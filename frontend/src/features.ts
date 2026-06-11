// Feature-vlaggen (trunk-based development): nieuwe features leven op main maar
// staan UIT tot ze klant-klaar zijn. De navigatie en routes verschijnen dan niet.
// Backend-tegenhanger: MAINTENANCE_ENABLED (env) in backend/main.py; zet beide
// aan om de feature te zien (lokaal: vlag hier true + MAINTENANCE_ENABLED=1).
export const FEATURES = {
  // Maintenance-sectie (predictive maintenance op motor-stroom, synthetische demo-data).
  maintenance: false,
};
