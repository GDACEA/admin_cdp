cargos_gestores_proyecto = [
    "JEFE DE PROYECTOS",
    "GERENTE DE PROYECTO",
    "COORDINADOR DE PROYECTOS",
    "JEFE DE ÁREA",
    "GERENTE GENERAL",
    "GERENTE DE CUMPLIMIENTO",
    "PROJECT MANAGEMENT PROFESSIONAL"
]

cargos_aplicables = [
    "PROFESIONAL AMBIENTAL",
    "ANALISTA DE LABORATORIO",
    "TECNICO DE TERRENO",
    "VETERINARIO",
    "PROFESIONAL DE TERRENO",
    "PROFESIONAL SIG",
    "LIDER DE CUADRILLA",
    "SUPERVISOR DE TERRENO",
    "ASESOR TECNICO",
    #"ANALISTA DE DATOS AMBIENTALES",
    "ASESOR SENIOR",
    "JEFE DE CUADRILLA",
    "COORDINADOR DE FAENA",
    "JEFE DE OPERACION DE MUESTREO",
    "PROFESIONAL DE DATOS AMBIENTALES",
    "JEFE SIG Y TELEDETECCION",
    "ANALISTA QUIMICO",
    "ESPECIALISTA",
    "TECNICO VIVERISTA"
]

PAGES_CONFIG = [
    {
        "label": "Gestión de Permisos",
        "icon": "🔐",
        "view": "views.gestion_de_permisos",
        "order": 2,
        "enabled": True,
        "roles": ["ADMIN"] + cargos_gestores_proyecto,
    },
    {
        "label": "Gestión de Terrenos",
        "icon": "🗺️",
        "view": "views.gestion_de_terrenos",
        "order": 1,
        "enabled": True,
        "roles": ["ADMIN"] + cargos_gestores_proyecto,
    },
    {
        "label": "Cumplimiento",
        "icon": "✅",
        "view": "views.cumplimiento_de_terreno",
        "order": 3,
        "enabled": True,
        "roles": ["ADMIN"] + cargos_gestores_proyecto,
    },
    {
        "label": "Administración",
        "icon": "⚙️",
        "view": "views.administracion",
        "order": 4,
        "enabled": True,
        "roles": ["ADMIN"],
    },
]
