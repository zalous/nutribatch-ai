-- ====================================================================
-- NutriBatch AI - Script de Inicialización de Base de Datos (Supabase)
-- 5 Tablas del Spec Técnico y Funcional
-- ====================================================================

-- 0. Habilitar extensión para generación de UUIDs (por defecto disponible en Postgres)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ====================================================================
-- TABLA 1: INVENTARIO
-- Nevera, congelador, despensa seca y tápers de batch cooking
-- ====================================================================
CREATE TABLE IF NOT EXISTS public.inventario (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre TEXT NOT NULL,
    ubicacion TEXT NOT NULL CHECK (ubicacion IN ('nevera', 'congelador', 'despensa', 'batch_cocinado')),
    cantidad_aprox TEXT NOT NULL,
    gramos_estimados NUMERIC,
    es_indivisible BOOLEAN DEFAULT FALSE,
    nutricion_por_comida_pareja JSONB,
    fecha_entrada DATE NOT NULL DEFAULT CURRENT_DATE,
    fecha_cocinado DATE,
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW())
);

CREATE INDEX IF NOT EXISTS idx_inventario_ubicacion ON public.inventario(ubicacion);
CREATE INDEX IF NOT EXISTS idx_inventario_fecha_cocinado ON public.inventario(fecha_cocinado);

-- ====================================================================
-- TABLA 2: DICCIONARIO_TICKETS
-- Memoria de supermercados para normalizar nombres y pesos
-- ====================================================================
CREATE TABLE IF NOT EXISTS public.diccionario_tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    texto_ticket TEXT UNIQUE NOT NULL,
    nombre_limpio TEXT NOT NULL,
    es_alimentacion BOOLEAN NOT NULL DEFAULT TRUE,
    supermercado TEXT,
    gramos_habituales NUMERIC,
    es_indivisible BOOLEAN DEFAULT FALSE,
    ubicacion_defecto TEXT NOT NULL DEFAULT 'despensa' CHECK (ubicacion_defecto IN ('nevera', 'congelador', 'despensa', 'hogar_no_inventariar')),
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW())
);

CREATE INDEX IF NOT EXISTS idx_diccionario_texto_ticket ON public.diccionario_tickets(texto_ticket);

-- ====================================================================
-- TABLA 3: RECETAS
-- Catálogo de recetas aprobadas y propuestas de batch cooking
-- ====================================================================
CREATE TABLE IF NOT EXISTS public.recetas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    titulo TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('batch_plato_cerrado', 'batch_componente', 'receta_suelta', 'desayuno', 'snack_merienda')),
    aprobada BOOLEAN NOT NULL DEFAULT FALSE,
    comidas_pareja_por_olla INTEGER NOT NULL DEFAULT 1,
    guia_emplatado TEXT,
    ingredientes_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    pasos_preparacion TEXT,
    nutricion_por_comida_pareja JSONB,
    ultima_vez_cocinada DATE,
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW())
);

CREATE INDEX IF NOT EXISTS idx_recetas_aprobada ON public.recetas(aprobada);
CREATE INDEX IF NOT EXISTS idx_recetas_tipo ON public.recetas(tipo);

-- ====================================================================
-- TABLA 4: REGISTRO_COMIDAS
-- Historial diario de consumo y cocinado de Gonzalo y Marta
-- ====================================================================
CREATE TABLE IF NOT EXISTS public.registro_comidas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fecha_consumo DATE NOT NULL DEFAULT CURRENT_DATE,
    fecha_cocinado DATE,
    momento TEXT NOT NULL CHECK (momento IN ('desayuno', 'comida', 'merienda', 'cena', 'snack')),
    receta_id UUID REFERENCES public.recetas(id) ON DELETE SET NULL,
    tipo_reparto TEXT NOT NULL DEFAULT 'estandar_55_45' CHECK (tipo_reparto IN ('estandar_55_45', 'mitad_50_50', 'solo_gonzalo', 'solo_marta')),
    descripcion TEXT,
    completado BOOLEAN NOT NULL DEFAULT TRUE,
    nutricion_gonzalo JSONB,
    nutricion_marta JSONB,
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW())
);

CREATE INDEX IF NOT EXISTS idx_registro_comidas_fecha ON public.registro_comidas(fecha_consumo);
CREATE INDEX IF NOT EXISTS idx_registro_comidas_receta_id ON public.registro_comidas(receta_id);

-- ====================================================================
-- TABLA 5: LISTA_COMPRA
-- Segundo cerebro unificado para comida, básicos y hogar
-- ====================================================================
CREATE TABLE IF NOT EXISTS public.lista_compra (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item TEXT NOT NULL,
    categoria TEXT NOT NULL DEFAULT 'frescos' CHECK (categoria IN ('frescos', 'despensa', 'congelados', 'hogar_y_otros')),
    origen TEXT NOT NULL DEFAULT 'manual_o_voz' CHECK (origen IN ('plan_recetas', 'manual_o_voz')),
    comprado BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_anadido DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW())
);

CREATE INDEX IF NOT EXISTS idx_lista_compra_comprado ON public.lista_compra(comprado);
CREATE INDEX IF NOT EXISTS idx_lista_compra_categoria ON public.lista_compra(categoria);

-- ====================================================================
-- POLÍTICAS DE SEGURIDAD (Row Level Security - RLS)
-- Permite lectura y escritura abierta para anon/authenticated
-- ====================================================================
ALTER TABLE public.inventario ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.diccionario_tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recetas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.registro_comidas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lista_compra ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Acceso total inventario" ON public.inventario FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Acceso total diccionario_tickets" ON public.diccionario_tickets FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Acceso total recetas" ON public.recetas FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Acceso total registro_comidas" ON public.registro_comidas FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Acceso total lista_compra" ON public.lista_compra FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
