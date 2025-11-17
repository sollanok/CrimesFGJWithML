import re, unicodedata, difflib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor
from sklearn.preprocessing import StandardScaler
from prophet import Prophet

from utils.database_queries import get_daily_affluence, get_metro_coords, get_all_crimes

# --------------------------------------------
# ---------- Compatibility Checks ------------
# --------------------------------------------
if not hasattr(np, "float"):  np.float  = float
if not hasattr(np, "int"):    np.int    = int
if not hasattr(np, "bool"):   np.bool   = bool
if not hasattr(np, "object"): np.object = object

# --------------------------------------------
# ---------------- Helpers -------------------
# --------------------------------------------
def fix_mojibake(s: str) -> str:
    if not isinstance(s, str): return s
    m = {"Ã¡":"á","Ã©":"é","Ã­":"í","Ã³":"ó","Ãº":"ú","Ã":"Á","Ã‰":"É","Ã":"Í","Ã“":"Ó","Ãš":"Ú",
         "Ã±":"ñ","Ã‘":"Ñ","Ã¼":"ü","Ãœ":"Ü","Â":""}
    for a,b in m.items(): s = s.replace(a,b)
    return unicodedata.normalize("NFC", s)

def canon_key_ascii(s: str) -> str:
    if s is None: return None
    t = fix_mojibake(str(s)).strip().lower()
    t = (t.replace("á","a").replace("é","e").replace("í","i")
          .replace("ó","o").replace("ú","u").replace("ñ","n").replace("ü","u"))
    t = re.sub(r"[^a-z0-9]+", "_", t)
    t = re.sub(r"_+", "_", t).strip("_")
    return t

def choose_station_key_once(query_str, keys_list):
    q = canon_key_ascii(query_str)
    cands_key = [k for k in keys_list if k == q]
    if cands_key:
        return cands_key[0], cands_key
    
    cands_substr = [k for k in keys_list if q in k]
    if not cands_substr:
        sug = difflib.get_close_matches(q, keys_list, n=10, cutoff=0.6)
        raise ValueError(f"No encontré coincidencias para '{q}'. Sugerencias: {', '.join(sug) if sug else '—'}")
    if q in cands_substr:
        return q, cands_substr
    return cands_substr[0], cands_substr

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1 = np.radians(lat1); p2 = np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat/2.0)**2 + np.cos(p1)*np.cos(p2)*np.sin(dlon/2.0)**2
    return 2 * R * np.arcsin(np.sqrt(a))

def _parse_hour(h):
    if pd.isna(h): return np.nan
    s = str(h).strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try: return pd.to_datetime(s, format=fmt).hour
        except Exception: pass
    try: return int(s.split(":")[0])
    except Exception: return np.nan

# --------------------------------------------
# ----------- Probability Reports ------------
# --------------------------------------------
def hour_day_probability_report(station_key, rb, co, radius_m=150, top_k_hours=3):
    skey = canon_key_ascii(station_key)
    row = co.loc[co["key"].map(canon_key_ascii) == skey]
    if row.empty: raise ValueError(f"No hay coordenadas para '{station_key}'")
    row = row.iloc[0]; st_lat, st_lon = float(row["lat"]), float(row["lon"])

    if "fecha_hecho" not in rb.columns:
        raise KeyError("Se espera columna 'fecha_hecho' en robos_filtrados")
    rb_loc = rb.dropna(subset=["lat","lon","fecha_hecho"]).copy()
    rb_loc["fecha_hecho"] = pd.to_datetime(rb_loc["fecha_hecho"], errors="coerce")
    rb_loc = rb_loc.dropna(subset=["fecha_hecho"])

    d_m = haversine_m(st_lat, st_lon, rb_loc["lat"].to_numpy(), rb_loc["lon"].to_numpy())
    rb_st = rb_loc.loc[d_m <= radius_m].copy()
    if rb_st.empty:
        print("No hay robos asignados a esta estación dentro del radio seleccionado.")
        return (pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(),
                {"best_dow":0,"best_hour_start":11,"best_hour_end":12,"hour_conf":0.0,
                 "tipo_prob":"desconocido","tipo_conf":0.0})

    rb_st["dow"] = rb_st["fecha_hecho"].dt.weekday
    dow_counts = rb_st["dow"].value_counts().sort_index()
    dow_probs = (dow_counts / dow_counts.sum() * 100).round(2)
    dias = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
    dow_df = pd.DataFrame({"dow": dow_probs.index,
                           "dia": [dias[i] for i in dow_probs.index],
                           "prob_%": dow_probs.values})

    if "hora_hecho" in rb_st.columns:
        h = pd.to_datetime(rb_st["hora_hecho"], errors="coerce").dt.hour
        if h.isna().all():
            h = rb_st["hora_hecho"].astype(str).str.extract(r"^(\d{1,2})")[0].astype(float)
        rb_st["hora"] = h
    elif "hora" in rb_st.columns:
        rb_st["hora"] = pd.to_numeric(rb_st["hora"], errors="coerce")
    else:
        rb_st["hora"] = np.nan
    rb_st = rb_st.dropna(subset=["hora"]).copy()
    rb_st["hora"] = rb_st["hora"].astype(int).clip(0, 23)

    hour_df = pd.DataFrame(columns=["hora","prob_%"])
    hour2_df = pd.DataFrame(columns=["hora_inicio","prob_%"])
    best_h_start, best_h_end, hour_conf = 11, 12, 0.0

    if len(rb_st) > 0 and rb_st["hora"].notna().any():
        hour_counts = rb_st["hora"].value_counts().reindex(range(24), fill_value=0)
        if hour_counts.sum() > 0:
            hour_probs = (hour_counts / hour_counts.sum() * 100).round(2)
            hour_df = pd.DataFrame({"hora": range(24), "prob_%": hour_probs.values})
            arr = hour_counts.to_numpy(); total = arr.sum()
            circ = np.concatenate([arr, arr[:1]])
            sums = np.convolve(circ, np.ones(2, dtype=int), "valid")[:24]
            best_h_start = int(np.argmax(sums)); best_h_end = (best_h_start + 1) % 24
            hour_conf = round(float(sums[best_h_start] / total * 100.0), 2)
            hour2_df = pd.DataFrame({"hora_inicio": range(24),
                                     "prob_%": (sums / total * 100.0).round(2)})

    tipo_prob, tipo_conf = "desconocido", 0.0
    tipo_top_df = pd.DataFrame(columns=["tipo","porcentaje"])
    for col in ["delito", "categoria_delito", "subcategoria","tipo"]:
        if col in rb_st.columns:
            counts = rb_st[col].astype(str).str.strip().str.lower().value_counts()
            if len(counts) > 0:
                tipo_prob = counts.index[0]
                tipo_conf = round(float(counts.iloc[0] / counts.sum() * 100.0), 2)
                tipo_top_df = (counts.head(5)/counts.sum()*100.0).round(2).reset_index()
                tipo_top_df.columns = ["tipo","porcentaje"]
            break

    meta = {
        "best_dow": int(dow_df.sort_values("prob_%", ascending=False).iloc[0]["dow"]) if len(dow_df) else 0,
        "best_hour_start": best_h_start,
        "best_hour_end": best_h_end,
        "hour_conf": hour_conf,
        "tipo_prob": tipo_prob,
        "tipo_conf": tipo_conf
    }
    return (dow_df, hour_df, hour2_df, tipo_top_df, meta)

# --------------------------------------------
# -------------- Seasonality -----------------
# --------------------------------------------
def _mx_basic_holidays():
    return set([
        "2023-01-01","2023-02-06","2023-03-20","2023-05-01","2023-09-16","2023-11-20","2023-12-25",
        "2024-01-01","2024-02-05","2024-03-18","2024-05-01","2024-09-16","2024-11-18","2024-12-25",
        "2025-01-01","2025-02-03","2025-03-17","2025-05-01","2025-09-16","2025-11-17","2025-12-25"
    ])

def add_time_features_daily(df):
    d = pd.to_datetime(df["ds"])
    df["dow"] = d.dt.weekday
    df["month"] = d.dt.month
    df["weekofyear"] = d.dt.isocalendar().week.astype(int)
    df["is_quincena"] = d.dt.day.isin([1,15]).astype(int)
    df["is_weekend"] = (df["dow"]>=5).astype(int)
    hol = _mx_basic_holidays()
    df["feriado"] = d.dt.strftime("%Y-%m-%d").isin(hol).astype(int)
    return df

def make_lags(df, col, L=[1,2,3,7,14]):
    for lag in L:
        df[f"{col}_lag{lag}"] = df[col].shift(lag)
    return df

def oversample_positives_local(d, col="robos", factor=3, seed=42):
    pos = d[d[col] > 0]
    if len(pos) == 0: return d.copy()
    dup = pos.sample(len(pos)*factor, replace=True, random_state=seed)
    out = pd.concat([d, dup], ignore_index=True).sort_values("ds")
    return out

# --------------------------------------------
# ------ DB Calling and Normalization --------
# --------------------------------------------
def load_and_normalize():
    af = get_daily_affluence()
    co = get_metro_coords()
    rb = get_all_crimes()

    if af.empty: raise ValueError("No se pudieron cargar datos de afluencia (daily_affluence).")
    if co.empty: raise ValueError("No se pudieron cargar coordenadas (lines_metro).")
    if rb.empty: raise ValueError("No se pudieron cargar crímenes (crimes_clean).")

    # 1. Reemplazar NaNs en la columna "key" por 195
    af["key"] = af["key"].fillna(195)
    # 2. Convertir float (e.g., 1.0) a int (e.g., 1)
    af["key"] = af["key"].astype(int)
    # 3. Convertir int a string (e.g., "1")
    af["key"] = af["key"].astype(str)

    af.columns = [c.lower() for c in af.columns]
    af["fecha"] = pd.to_datetime(af["fecha"], errors="coerce")
    af = af.dropna(subset=["fecha"])
    if "afluencia" not in af.columns:
        raise KeyError("La tabla 'daily_affluence' debe tener la columna 'afluencia'.")
    af["afluencia"] = pd.to_numeric(af["afluencia"], errors="coerce").fillna(0)


    # 3. Normalizar CO (Coordenadas)
    co.columns = [c.lower() for c in co.columns]

    co = co.dropna(subset=["key"])
    co["key"] = co["key"].astype(str)

    # 'key', 'lat', 'lon' ya vienen de la consulta
    for c in ["lat","lon"]:
        if c not in co.columns: raise KeyError(f"La tabla 'lines_metro' debe tener '{c}'.")
    co["lat"] = pd.to_numeric(co["lat"], errors="coerce")
    co["lon"] = pd.to_numeric(co["lon"], errors="coerce")
    # 'key' es la PK de la estación ('num'), 'nombre' es el nombre legible
    co = co.dropna(subset=["key","lat","lon"]).drop_duplicates(subset=["key"])

    # 4. Normalizar RB (Robos)
    rb.columns = [c.lower() for c in rb.columns]
    # 'fecha_hecho', 'lat', 'lon' ya vienen de la consulta
    if "fecha_hecho" not in rb.columns:
        raise KeyError("La tabla 'crimes_clean' debe tener 'fecha_hecho'.")
    rb["fecha_hecho"] = pd.to_datetime(rb["fecha_hecho"], errors="coerce")
    rb = rb.dropna(subset=["fecha_hecho","lat","lon"]).copy()

    if "hora_hecho" in rb.columns: rb["hora_int"] = rb["hora_hecho"].apply(_parse_hour)
    else: rb["hora_int"] = np.nan

    # El script original busca 'categoria_delito', 'delito', etc.
    # Nuestra consulta 'get_all_crimes' solo trae 'delito', así que la encontrará.
    _tipo_cols = [c for c in ["categoria_delito","delito","subcategoria","tipo"] if c in rb.columns]
    if _tipo_cols:
        rb["tipo_robo"] = (rb[_tipo_cols[0]].astype(str).str.strip().str.lower()
                            .str.normalize("NFKD").str.encode("ascii", errors="ignore").str.decode("ascii"))
    else:
        rb["tipo_robo"] = "desconocido"

    # Filtrar robos al rango de fechas de afluencia
    fmin, fmax = af["fecha"].min(), af["fecha"].max()
    if pd.isna(fmin) or pd.isna(fmax):
        raise ValueError("No se pudo determinar el rango de fechas de la afluencia.")
        
    rb = rb[(rb["fecha_hecho"]>=fmin) & (rb["fecha_hecho"]<=fmax)].copy()
    
    return af, co, rb

# --------------------------------------------
# ------------- Building Stats ---------------
# --------------------------------------------
def build_daily_station_frame(af, co, rb, station_key, radius_m=100):
    row = co.loc[co["key"].map(canon_key_ascii) == station_key]
    if row.empty: raise ValueError(f"No hay coordenadas para '{station_key}'.")
    st_lat = float(row.iloc[0]["lat"]); st_lon = float(row.iloc[0]["lon"])

    d_m = haversine_m(st_lat, st_lon, rb["lat"].to_numpy(), rb["lon"].to_numpy())
    rb_st = rb.loc[d_m <= radius_m].copy()
    rb_st["ds"] = pd.to_datetime(rb_st["fecha_hecho"].dt.date)
    rob_d = rb_st.groupby("ds").size().rename("robos").to_frame()

    # 'station_key' of af (af['key']) MUST be the same as co (co['key'])
    af_st = af[af["key"].map(canon_key_ascii) == station_key].copy()
    if af_st.empty: raise ValueError(f"No tengo afluencia para '{station_key}'.")
    af_st = af_st[["fecha","afluencia"]].dropna().rename(columns={"fecha":"ds"})
    af_d = (af_st.set_index("ds").resample("D")["afluencia"].sum().to_frame().reset_index())

    df = pd.merge(af_d, rob_d, on="ds", how="left").sort_values("ds")
    df["robos"] = df["robos"].fillna(0)

    df["aflu_ma7"]  = df["afluencia"].rolling(7, min_periods=1).mean()
    df["aflu_ma14"] = df["afluencia"].rolling(14, min_periods=1).mean()
    df["ratio"]    = df["robos"] / (df["afluencia"] + 1.0)

    df = add_time_features_daily(df)
    df = make_lags(df, "robos", L=[1,2,3,7,14])
    df = make_lags(df, "afluencia", L=[1,2,3,7,14])

    df = df.dropna().reset_index(drop=True)
    return df, rb_st

# --------------------------------------------
# ---- Splitting Data Depending On Size ------
# --------------------------------------------
def split_series_chron(df, test_frac=0.15, val_frac=0.15):
    n = len(df)
    n_test = int(round(n*test_frac))
    n_val  = int(round(n*val_frac))
    n_train = n - n_val - n_test
    if n_train < 50:
        print(f"Warning: Too few data rows (n={n}), adjusting splits.")
        n_test = max(1, int(n * 0.2))
        n_val = 0
        n_train = n - n_test
    
    return df.iloc[:n_train].copy(), df.iloc[n_train:n_train+n_val].copy(), df.iloc[n_train+n_val:].copy()

def _align(part: pd.DataFrame, feat_cols, strict=True) -> pd.DataFrame:
    out = part.copy()
    for c in feat_cols:
        if c not in out.columns:
            out[c] = np.nan
    cols = ["ds","robos"] + list(feat_cols)
    out = out[cols]
    if strict:
        return out.dropna()
    out = out.dropna(subset=["ds","robos"])
    lag_like = [c for c in feat_cols if ("lag" in c) or (c == "yhat_prophet")]
    other = [c for c in feat_cols if c not in lag_like]
    if len(lag_like):
        out[lag_like] = out[lag_like].fillna(method="ffill")
        out[lag_like] = out[lag_like].fillna(0.0)
    if len(other):
        out[other] = out[other].fillna(0.0)
    return out.reset_index(drop=True)

def fit_models_daily(df):
    if len(df) < 60:
        raise ValueError(f"Datos insuficientes para entrenar (n={len(df)}). Se necesitan al menos 60 días de datos limpios.")

    df_tr, df_va, df_te = split_series_chron(df, test_frac=0.15, val_frac=0.15)
    print(f"Splits (daily) → train:{df_tr.shape}  val:{df_va.shape}  test:{df_te.shape}")

    df_tr_os = oversample_positives_local(df_tr, col="robos", factor=3)

    prop = Prophet(daily_seasonality=True, weekly_seasonality=True, yearly_seasonality=True)
    prop.fit(df_tr_os[["ds","robos"]].rename(columns={"robos":"y"}))

    df_tr["yhat_prophet"] = prop.predict(df_tr[["ds"]])["yhat"].values
    if len(df_va) > 0:
        df_va["yhat_prophet"] = prop.predict(df_va[["ds"]])["yhat"].values
    if len(df_te) > 0:
        df_te["yhat_prophet"] = prop.predict(df_te[["ds"]])["yhat"].values

    feat_cols = [c for c in df.columns if c not in ["ds","robos"]] + ["yhat_prophet"]

    df_tr_os = df_tr_os.merge(
        prop.predict(df_tr_os[["ds"]])[["ds","yhat"]].rename(columns={"yhat":"yhat_prophet"}),
        on="ds", how="left"
    )
    df_tr_os = _align(df_tr_os, feat_cols, strict=True)
    if len(df_va) > 0: df_va = _align(df_va, feat_cols, strict=False)
    if len(df_te) > 0: df_te = _align(df_te, feat_cols, strict=False)

    if len(df_tr_os) == 0:
        raise ValueError("Train quedó vacío tras el alineado. Revisa lags/NA en datos.")
    if len(df_va) == 0:
        print("Val quedó vacía tras el alineado; entreno sin eval_set.")
    if len(df_te) == 0:
        print("Test quedó vacía tras el alineado; no se imprimirán métricas de test.")

    X_tr, y_tr = df_tr_os[feat_cols].values, df_tr_os["robos"].values
    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X_tr)

    X_va_s, y_va = None, None
    if len(df_va) > 0:
        X_va, y_va = df_va[feat_cols].values, df_va["robos"].values
        X_va_s = scaler.transform(X_va)

    X_te_s, y_te = None, None
    if len(df_te) > 0:
        X_te, y_te = df_te[feat_cols].values, df_te["robos"].values
        X_te_s = scaler.transform(X_te)

    xgb = XGBRegressor(
        objective="count:poisson",
        n_estimators=1200, max_depth=6, learning_rate=0.03,
        subsample=0.9, colsample_bytree=0.85, min_child_weight=1.0,
        reg_alpha=0.5, reg_lambda=4.0, random_state=42,
        tree_method="hist", eval_metric="rmse",
        early_stopping_rounds=50
    )
    
    fit_params = {
    "verbose": False
    }

    if X_va_s is not None and len(X_va_s) > 0:
        fit_params["eval_set"] = [(X_va_s, y_va)]
    else:
        print("Nota: No hay set de validación, se entrenará sin 'early stopping'.")

    xgb.fit(X_tr_s, y_tr, **fit_params)

    return prop, scaler, xgb, feat_cols, (df_tr, df_va, df_te)

# --------------------------------------------
# -------------- Forecasting -----------------
# --------------------------------------------
def forecast_28d_daily_and_aggregate_weekly(df, prop, scaler, xgb, feat_cols,
                                            base_lambda_week=None, alpha=0.7):
    last_day = pd.to_datetime(df["ds"]).max()
    future_days = pd.date_range(last_day + pd.Timedelta(days=1), periods=28, freq="D")
    fut = pd.DataFrame({"ds": future_days})

    fut["yhat_prophet"] = prop.predict(fut[["ds"]])["yhat"].values

    last_aflu = df["afluencia"].tail(14).median()
    fut["afluencia"] = last_aflu
    fut["aflu_ma7"]  = last_aflu
    fut["aflu_ma14"] = last_aflu
    fut["ratio"]     = 0.0

    fut = add_time_features_daily(fut)

    hist_tail = df[["ds","robos","afluencia","aflu_ma7","aflu_ma14","ratio",
                    "dow","month","weekofyear","is_quincena","is_weekend","feriado"]].tail(30)
    roll = pd.concat([hist_tail, fut], ignore_index=True)
    for L in [1,2,3,7,14]:
        roll[f"afluencia_lag{L}"] = roll["afluencia"].shift(L)
        roll[f"robos_lag{L}"] = roll["robos"].shift(L)

    future_feat = roll.tail(28).copy()
    for c in feat_cols:
        if c not in future_feat.columns:
            future_feat[c] = 0.0
    future_feat = future_feat[feat_cols].fillna(method="ffill").fillna(0.0)

    XF  = scaler.transform(future_feat.values)
    yF  = np.clip(xgb.predict(XF), 0, None)

    daily_pred = pd.DataFrame({
        "ds": future_days,
        "robos_pred_xgb_diario": np.round(yF, 3),
        "yhat_prophet_diario": np.round(future_feat["yhat_prophet"].values, 3)
    })

    wk = (daily_pred.set_index("ds")
                    .resample("W-SUN")
                    .agg({"robos_pred_xgb_diario":"sum","yhat_prophet_diario":"sum"}))\
                    .rename(columns={"robos_pred_xgb_diario":"robos_pred_xgb",
                                     "yhat_prophet_diario":"yhat_prophet"})\
                    .reset_index()

    if base_lambda_week is None or not np.isfinite(base_lambda_week) or base_lambda_week < 0:
        base_lambda_week = max(0.0, float(df["robos"].mean()) * 7.0)

    wk["robos_pred_xgb_shrunk"] = (
        alpha * wk["robos_pred_xgb"].clip(lower=0) +
        (1.0 - alpha) * base_lambda_week
    )
    wk["prob_semana_%"] = (1.0 - np.exp(-wk["robos_pred_xgb_shrunk"])) * 100.0
    wk["prob_semana_%"] = wk["prob_semana_%"].round(2)

    def _risk_label(p):
        if p < 15:  return "Bajo"
        if p < 35:  return "Medio"
        return "Alto"
    wk["riesgo"] = wk["prob_semana_%"].apply(_risk_label)

    return wk, daily_pred

def enrich_with_calendar(pred_week_df, rb, co, station_key, radius_m=150):
    dow_df, hour_df, hour2_df, tipo_top_df, meta = hour_day_probability_report(
        station_key, rb, co, radius_m=radius_m, top_k_hours=3
    )
    def _dow_name(d): return ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"][int(d)]
    rows = []
    for _, r in pred_week_df.iterrows():
        ds = pd.to_datetime(r["ds"])
        week_start = ds - pd.Timedelta(days=6)
        best_dow = int(meta["best_dow"])
        best_date = (week_start + pd.Timedelta(days=best_dow)).date()
        h0, h1 = meta["best_hour_start"], meta["best_hour_end"]
        hour_window = f"{h0:02d}:00-{h1:02d}:59" if h1 >= h0 else f"{h0:02d}:00-{h1:02d}:59 (cruza medianoche)"
        rows.append({
            "ds": ds,
            "robos_pred_xgb": r.get("robos_pred_xgb_shrunk", r["robos_pred_xgb"]),
            "yhat_prophet": r["yhat_prophet"],
            "prob_semana_%": r.get("prob_semana_%", np.nan),
            "riesgo": r.get("riesgo", None),
            "dia_probable": _dow_name(best_dow),
            "fecha_probable": str(best_date),
            "hora_rango_probable": hour_window,
            "tipo_probable": meta["tipo_prob"],
            "conf_tipo_%": meta["tipo_conf"]
        })
    pred_enriched = pd.DataFrame(rows)
    return pred_enriched, (dow_df, hour_df, hour2_df, tipo_top_df)

def get_available_stations():
    try:
        co = get_metro_coords()
        if co.empty:
            return pd.DataFrame(columns=['key', 'nombre', 'lat', 'lon'])
        
        co['nombre'] = co['nombre'].apply(lambda x: fix_mojibake(str(x)).strip().title())
        co = co.dropna(subset=['key', 'nombre', 'lat', 'lon'])
        co = co.sort_values('nombre')
        return co[['key', 'nombre', 'lat', 'lon']]
        
    except Exception as e:
        print(f"Error al cargar estaciones: {e}")
        return pd.DataFrame(columns=['key', 'nombre', 'lat', 'lon'])

# --------------------------------------------
# --------------- Full Model -----------------
# --------------------------------------------
def run_full_prediction_pipeline(station_key_or_name: str, radius_m: int = 100):
    print(f"Iniciando pipeline para: {station_key_or_name}, radio: {radius_m}m")
    
    try:
        af, co, rb = load_and_normalize()
        print(f"Datos cargados: af={af.shape}, co={co.shape}, rb={rb.shape}")
    except Exception as e:
        print(f"Error en load_and_normalize: {e}")
        raise ValueError(f"Error al cargar datos base: {e}")

    keys_from_coords = co["key"].dropna().unique().tolist()
    keys_from_aflu = af["key"].dropna().unique().tolist()
    
    keys_list = sorted(list(set(keys_from_coords) & set(keys_from_aflu)))
    
    if not keys_list:
        raise ValueError("No hay estaciones que tengan *tanto* coordenadas como datos de afluencia.")

    co_map = co.set_index(co['nombre'].map(canon_key_ascii))['key'].map(canon_key_ascii).to_dict()
    q_canon = canon_key_ascii(station_key_or_name)
    
    selected_key = None
    if q_canon in co_map:
        selected_key = co_map[q_canon]
    
    if selected_key is None and q_canon in keys_list:
        selected_key = q_canon
        
    if selected_key is None:
        try:
            selected_key, cands = choose_station_key_once(station_key_or_name, keys_list)
            print(f"Input '{station_key_or_name}' resuelto a '{selected_key}' de {cands}")
        except ValueError as e:
             raise ValueError(f"No se encontró la estación '{station_key_or_name}'. Error: {e}")
    
    if selected_key not in keys_list:
        raise ValueError(f"Estación '{selected_key}' no tiene datos completos (coordenadas Y afluencia).")

    print(f"Usando estación (key): {selected_key}")

    try:
        df_daily, rb_st = build_daily_station_frame(af, co, rb, selected_key, radius_m=radius_m)
        print(f"DataFrame diario construido: {df_daily.shape}")
    except Exception as e:
        print(f"Error en build_daily_station_frame: {e}")
        raise ValueError(f"Error al construir la serie de tiempo: {e}")

    if df_daily.empty:
        raise ValueError(f"No se generaron datos diarios para '{selected_key}'. (¿Sin afluencia?)")

    base_lambda_daily = float(df_daily["robos"].mean())
    base_lambda_week  = float(df_daily.set_index("ds")["robos"].resample("W-SUN").sum().mean())
    if not np.isfinite(base_lambda_week) or base_lambda_week < 0:
        base_lambda_week = max(0.0, base_lambda_daily * 7.0)
    print(f"Lambdas base: daily={base_lambda_daily:.4f}, weekly={base_lambda_week:.4f}")

    try:
        prop, scaler, xgb, feat_cols, splits = fit_models_daily(df_daily)
        print("Modelos (Prophet + XGB) entrenados.")
    except Exception as e:
        print(f"Error en fit_models_daily: {e}")
        raise ValueError(f"Error al entrenar modelos: {e}")

    pred_week_raw, pred_daily = forecast_28d_daily_and_aggregate_weekly(
        df_daily, prop, scaler, xgb, feat_cols,
        base_lambda_week=base_lambda_week, alpha=0.70
    )
    print("Predicción de 4 semanas generada.")

    pred_enriched, (dow_df, hour_df, hour2_df, tipo_top_df) = enrich_with_calendar(
        pred_week_raw, rb, co, selected_key, radius_m=radius_m
    )
    print("Reportes de calendario generados.")

    station_name_readable = "Desconocida"
    try:
        station_name_readable = co.loc[co['key'].map(canon_key_ascii) == selected_key, 'nombre'].iloc[0]
    except Exception:
        pass

    return {
        "station_name": station_name_readable,
        "station_key": selected_key,
        "radius": radius_m,
        "pred_enriched": pred_enriched,
        "prob_dow": dow_df,
        "prob_hour": hour_df,
        "prob_hour_2h": hour2_df,
        "prob_tipo": tipo_top_df,
        "daily_history": df_daily
    }