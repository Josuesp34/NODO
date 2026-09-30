export const featureContracts = {
  athleteProfile: {
    label: "Perfil deportivo",
    endpoint: (athleteId: number) => `athletes/${athleteId}/profile`,
    expected: "GET y PUT /athletes/{athlete_id}/profile",
  },
  checkins: {
    label: "Check-in diario",
    endpoint: "athletes/{athlete_id}/checkins/{local_date}",
    expected: "PUT /athletes/{athlete_id}/checkins/{local_date}",
  },
  complaints: {
    label: "Molestias",
    endpoint: "athletes/{athlete_id}/complaints",
    expected: "GET y POST /athletes/{athlete_id}/complaints; POST /complaints/{id}/updates",
  },
  connections: {
    label: "Conexiones",
    endpoint: "athletes/{athlete_id}/connections/intervals",
    expected: "GET, POST y DELETE /athletes/{athlete_id}/connections/intervals; OAuth real pendiente",
  },
  fitUpload: {
    label: "Carga FIT segura",
    endpoint: "athletes/{athlete_id}/activities/fit",
    expected: "POST autenticado /athletes/{athlete_id}/activities/fit",
  },
  review: {
    label: "Bandeja de revisión",
    endpoint: "review-items",
    expected: "GET /review-items y POST /review-items/{id}/decision",
  },
  recommendations: {
    label: "Propuestas",
    endpoint: "recommendations",
    expected: "GET y POST /recommendations; POST /recommendations/{id}/decision",
  },
  groups: {
    label: "Grupos",
    endpoint: "groups",
    expected: "GET y POST /groups; GET y POST /groups/{id}/members",
  },
  templates: {
    label: "Plantillas",
    endpoint: "templates",
    expected: "GET y POST /templates; POST /templates/{id}/apply",
  },
  consents: {
    label: "Consentimientos",
    endpoint: "consents",
    expected: "GET y POST /consents; DELETE /consents/{id}",
  },
  dataExport: {
    label: "Exportación de datos",
    endpoint: "account/export",
    expected: "GET /account/export",
  },
} as const;
