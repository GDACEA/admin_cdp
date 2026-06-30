ruta_nas = '/mnt/bd_historico'

output_teck = 'CreacionMasivaFichas'

ruta_agrupados = '/mnt/bd_historico/TECK/096/data'


engine_string_prod = "postgresql://gda_prod:Cea2025.!@172.20.4.17:5432/"


USERS_GDA = {
    #'admin': 'cb9ab108fd20690ee83903302f5fecb49a516ab772d629800ddb8b2bb6d2f2a5',
    'admin': 'Cea2025.!',
 'gbarrios': '30c506211d0910532c4e0378641f55e73fb6da4c20a57d3d03b2731ff385bbcb',
 'ggacitua': 'password',
 'jaravenap': '73eff7a6c4ff7ee6688b7dd12bc60af7b6533170b04b0180ee536a42e8e541ca',
 'jvalladares': '3c36cb110a624bb9107607640db5b9ea6256d28b499f4b759620d78d62e72c56',
 'vcabrera': '08981b6891bd3654a19b7e40e0bc9ed31382891d3d95e38eaacef3bdbcd6f6a4',
 }


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
