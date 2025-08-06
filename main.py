import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate
import google.generativeai as genai
import os
import re
import time
import zipfile
from io import BytesIO

# --- CONFIGURACIÓN DE LA PÁGINA DE STREAMLIT ---
st.set_page_config(
    page_title="Ensamblador de Fichas Técnicas con IA",
    page_icon="🤖",
    layout="wide"
)

# --- FUNCIONES DE LÓGICA ---

# Función para limpiar HTML (de tu código original)
def limpiar_html(texto_html):
    if not isinstance(texto_html, str):
        return texto_html
    cleanr = re.compile('<.*?>')
    texto_limpio = re.sub(cleanr, '', texto_html)
    return texto_limpio

# Función para configurar el modelo Gemini
def setup_model(api_key):
    try:
        genai.configure(api_key=api_key)
        generation_config = {
            "temperature": 0.6, "top_p": 1, "top_k": 1, "max_output_tokens": 8192
        }
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
        model = genai.GenerativeModel(
            model_name="gemini-1.5-pro-latest",
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        return model
    except Exception as e:
        st.error(f"Error al configurar la API de Google: {e}")
        return None

# Funciones para construir prompts (adaptadas de tu código)
def construir_prompt_analisis(fila):
    fila = fila.fillna('')
    descripcion_item = (
        f"Enunciado: {fila.get('Enunciado', '')}\n"
        f"A. {fila.get('OpcionA', '')}\n" # Asegúrate de que el Excel tenga 'OpcionA', 'OpcionB', etc.
        f"B. {fila.get('OpcionB', '')}\n"
        f"C. {fila.get('OpcionC', '')}\n"
        f"D. {fila.get('OpcionD', '')}\n"
        f"Respuesta correcta: {fila.get('AlternativaClave', '')}"
    )
    return f"""
🎯 ROL DEL SISTEMA
Eres un experto en evaluación educativa con un profundo conocimiento de la pedagogía urbana, especializado en lectura y procesos cognitivos en el contexto de Bogotá. Tu misión es analizar un ítem de evaluación para proporcionar un análisis tripartito: un resumen de lo que evalúa, la ruta cognitiva detallada para la respuesta correcta, y un análisis de los errores asociados a las opciones incorrectas.

🧠 INSUMOS DE ENTRADA
- Descripción del Ítem: {descripcion_item}
- Componente: {fila.get('ComponenteNombre', 'No aplica')}
- Competencia: {fila.get('CompetenciaNombre', '')}
- Aprendizaje Priorizado: {fila.get('AfirmacionNombre', '')}
- Evidencia de Aprendizaje: {fila.get('EvidenciaNombre', '')}
- Grado Escolar: {fila.get('ItemGradoId', '')}
- Respuesta correcta: {fila.get('AlternativaClave', 'No aplica')}
- Opción A: {fila.get('OpcionA', 'No aplica')}
- Opción B: {fila.get('OpcionB', 'No aplica')}
- Opción C: {fila.get('OpcionC', 'No aplica')}
- Opción D: {fila.get('OpcionD', 'No aplica')}

📝 INSTRUCCIONES PARA EL ANÁLISIS DEL ÍTEM
Genera el análisis del ítem siguiendo estas reglas y en el orden exacto solicitado:

### 1. Qué Evalúa
**Regla de Oro:** La descripción debe ser una síntesis directa y precisa de la taxonomía del ítem que tiene en cuenta la forma en que se resuelve el ítem.
- Redacta una única frase (máximo 2 renglones) que comience obligatoriamente con "Este ítem evalúa la capacidad del estudiante para...".
- La frase debe construirse usando la **Evidencia de Aprendizaje** como núcleo de la habilidad y la **Competencia** como el marco general.
- **Prohibido** referirse al contenido o a los personajes del texto. 

### 2. Ruta Cognitiva Correcta
Describe, en un párrafo continuo y de forma impersonal, el procedimiento mental que un estudiante debe ejecutar para llegar a la respuesta correcta.
- Debes articular la ruta usando **verbos que representen procesos cognitivos** (ej: identificar, relacionar, inferir, comparar, evaluar) para mostrar la secuencia de pensamiento de manera explícita.
- El último paso de la ruta debe ser la justificación final de por qué la alternativa clave es la única respuesta válida, conectando el razonamiento con la selección de esa opción.

### 3. Análisis de Opciones No Válidas (Distractores)
Para cada una de las TRES opciones incorrectas, realiza un análisis del error.
- Primero, identifica la **naturaleza de la confusión** (ej: es una lectura literal cuando se pide inferir, una sobregeneralización, una interpretación de un detalle irrelevante pero llamativo, una opinión personal no sustentada en el texto, etc.).
- Luego, explica el posible razonamiento que lleva al estudiante a cometer ese error.
- Finalmente, clarifica por qué esa opción es incorrecta en el contexto de la tarea evaluativa.

✍️ FORMATO DE SALIDA DEL ANÁLISIS
**REGLA CRÍTICA:** Responde únicamente con el texto solicitado y en la estructura definida a continuación. Es crucial que los tres títulos aparezcan en la respuesta, en el orden correcto y sin texto introductorio, de cierre o conclusiones.

Qué Evalúa:
Este ítem evalúa la capacidad del estudiante para [síntesis de la taxonomía, centrada en la Evidencia de Aprendizaje y el proceso para resolver el ítem].

Ruta Cognitiva Correcta:
Para resolver correctamente este ítem, el estudiante primero debe [verbo cognitivo 1]... Luego, necesita [verbo cognitivo 2]... Este proceso le permite [verbo cognitivo 3]..., lo que finalmente lo lleva a concluir que la opción [letra de la respuesta correcta] es la correcta porque [justificación final].

Análisis de Opciones No Válidas:
- **Opción [Letra del distractor]:** El estudiante podría escoger esta opción si comete un error de [naturaleza de la confusión], lo que lo lleva a pensar que [razonamiento erróneo]. Sin embargo, esto es incorrecto porque [razón clara y concisa].
- **Opción [Letra del distractor]:** La elección de esta alternativa sugiere una falla en [naturaleza de la confusión]. El estudiante posiblemente cree que [razonamiento erróneo], pero la opción es inválida debido a que [razón clara y concisa].
- **Opción [Letra del distractor]:** Esta opción funciona como un distractor para quien [naturaleza de la confusión], interpretando erróneamente que [razonamiento erróneo]. Es incorrecta puesto que [razón clara y concisa].
"""

def construir_prompt_recomendaciones(fila):
    fila = fila.fillna('')
    return f"""
🎯 ROL DEL SISTEMA
Eres un experto en evaluación educativa con un profundo conocimiento de la pedagogía urbana. Tu misión es generar dos recomendaciones pedagógicas personalizadas a partir de cada ítem de evaluación formativa: una para Fortalecer y otra para Avanzar en el aprendizaje. Deberás identificar de manera endógena los verbos clave de los procesos cognitivos implicados, basándote en la competencia, el aprendizaje priorizado, la evidencia de aprendizaje, la tipología textual (cuando aplique), el grado escolar y el nivel educativo general de los estudiantes. Luego, integrarás estos verbos de forma fluida en la redacción de las recomendaciones. Considerarás las características cognitivas y pedagógicas del ítem y el texto (cuando aplique), así como las particularidades de los estudiantes.

🧠 INSUMOS DE ENTRADA
- Texto/Fragmento: {fila.get('ItemContexto', 'No aplica')}
- Descripción del Ítem: {fila.get('ItemEnunciado', 'No aplica')}
- Componente: {fila.get('ComponenteNombre', 'No aplica')}
- Competencia: {fila.get('CompetenciaNombre', '')}
- Aprendizaje Priorizado: {fila.get('AfirmacionNombre', '')}
- Evidencia de Aprendizaje: {fila.get('EvidenciaNombre', '')}
- Tipología Textual (Solo para Lectura Crítica): {fila.get('Tipologia Textual', 'No aplica')}
- Grado Escolar: {fila.get('ItemGradoId', '')}
- Análisis de Errores Comunes: {fila.get('Analisis_Errores', 'No aplica')}
- Respuesta correcta: {fila.get('AlternativaClave', 'No aplica')}
- Opción A: {fila.get('OpcionA', 'No aplica')}
- Opción B: {fila.get('OpcionB', 'No aplica')}
- Opción C: {fila.get('OpcionC', 'No aplica')}
- Opción D: {fila.get('OpcionD', 'No aplica')}

📝 INSTRUCCIONES PARA GENERAR LAS RECOMENDACIONES
Genera las dos recomendaciones adhiriéndote estrictamente a lo siguiente:

### 1. Recomendación para FORTALECER 💪
- **Objetivo Central:** Andamiar el proceso cognitivo exacto descrito en la **Evidencia de Aprendizaje**.
- **Contexto Pedagógico:** La actividad debe ser un microcosmos de dicha evidencia, pero simplificada. Debes **descomponer el proceso cognitivo en pasos manejables**.
- **Actividad Propuesta:** Diseña una actividad de lectura que sea **novedosa, creativa y lúdica**. **Evita explícitamente ejercicios típicos** como cuestionarios, llenar espacios en blanco o buscar ideas principales de forma tradicional. La actividad debe ser útil para los profesores.
- **Preguntas Orientadoras:** Formula preguntas que funcionen como un **"paso a paso" del razonamiento**, guiando al estudiante a través del proceso de forma sutil.

### 2. Recomendación para AVANZAR 🚀
- **Objetivo Central:** Asegurar una **progresión cognitiva clara y directa** desde la habilidad de Fortalecer.
- **Contexto Pedagógico:** La actividad para Avanzar debe ser la **evolución natural y más compleja de la habilidad trabajada en Fortalecer**. La conexión entre ambas debe ser explícita y lógica.
- **Actividad Propuesta:** Diseña un desafío intelectual de lectura o análisis comparativo que sea **estimulante y poco convencional**. La actividad debe promover el pensamiento crítico y la transferencia de habilidades de una manera que no sea habitual en el aula.
- **Preguntas Orientadoras:** Formula preguntas abiertas que exijan **evaluación, síntesis, aplicación o metacognición**, demostrando un salto cualitativo respecto a las preguntas de Fortalecer.

✍️ FORMATO DE SALIDA DE LAS RECOMENDACIONES
**IMPORTANTE: Responde de forma directa, usando obligatoriamente la siguiente estructura. No añadas texto adicional.**
- **Redacción Impersonal:** Utiliza siempre una redacción profesional e impersonal (ej. "se sugiere al docente", "la tarea consiste en", "se entregan tarjetas").
- **Sin Conclusiones:** Termina directamente con la lista de preguntas.

RECOMENDACIÓN PARA FORTALECER EL APRENDIZAJE EVALUADO EN EL ÍTEM
Para fortalecer la habilidad de [verbo clave extraído de la Evidencia de Aprendizaje], se sugiere al docente [descripción de la estrategia de andamiaje para ese proceso exacto].
Una actividad que se puede hacer es: [Descripción detallada de la actividad novedosa y creativa, que no implica escritura].
Las preguntas orientadoras para esta actividad, entre otras, pueden ser:
- [Pregunta 1: Que guíe el primer paso del proceso cognitivo]
- [Pregunta 2: Que ayude a analizar un componente clave del proceso]
- [Pregunta 3: Que conduzca a la conclusión del proceso base]

RECOMENDACIÓN PARA AVANZAR EN EL APRENDIZAJE EVALUADO EN EL ÍTEM
Para avanzar desde [proceso cognitivo de Fortalecer] hacia la habilidad de [verbo clave del proceso cognitivo superior], se sugiere al docente [descripción de la estrategia de complejización].
Una actividad que se puede hacer es: [Descripción detallada de la actividad estimulante y poco convencional, que no implique escritura].
Las preguntas orientadoras para esta actividad, entre otras, pueden ser:
- [Pregunta 1: De análisis o evaluación que requiera un razonamiento más profundo]
- [Pregunta 2: De aplicación, comparación o transferencia a un nuevo contexto]
- [Pregunta 3: De metacognición o pensamiento crítico sobre el proceso completo]
"""


# --- INTERFAZ PRINCIPAL DE STREAMLIT ---

st.title("🤖 Ensamblador de Fichas Técnicas con IA")
st.markdown("Una aplicación para enriquecer datos pedagógicos y generar fichas personalizadas.")

# Inicializar session_state para guardar los datos entre ejecuciones
if 'df_enriquecido' not in st.session_state:
    st.session_state.df_enriquecido = None
if 'zip_buffer' not in st.session_state:
    st.session_state.zip_buffer = None

# --- PASO 0: Clave API ---
st.sidebar.header("🔑 Configuración Obligatoria")
api_key = st.sidebar.text_input("Ingresa tu Clave API de Google AI", type="password")

# --- PASO 1: Carga de Archivos ---
st.header("Paso 1: Carga tus Archivos")
col1, col2 = st.columns(2)
with col1:
    archivo_excel = st.file_uploader("Sube tu Excel con los datos base", type=["xlsx"])
with col2:
    archivo_plantilla = st.file_uploader("Sube tu Plantilla de Word", type=["docx"])

# --- PASO 2: Enriquecimiento con IA ---
st.header("Paso 2: Enriquece tus Datos con IA")
if st.button("🤖 Iniciar Análisis y Generación", disabled=(not api_key or not archivo_excel)):
    if not api_key:
        st.error("Por favor, ingresa tu clave API en la barra lateral izquierda.")
    elif not archivo_excel:
        st.warning("Por favor, sube un archivo Excel para continuar.")
    else:
        model = setup_model(api_key)
        if model:
            with st.spinner("Procesando archivo Excel y preparando datos..."):
                df = pd.read_excel(archivo_excel)
                # Limpieza de HTML
                for col in df.columns:
                    if df[col].dtype == 'object':
                        df[col] = df[col].apply(limpiar_html)
                st.success("Datos limpios y listos para el análisis.")

            total_filas = len(df)
            
            # Proceso de Análisis
            with st.spinner("Generando Análisis de Ítems... Esto puede tardar varios minutos."):
                que_evalua_lista, just_correcta_lista, an_distractores_lista = [], [], []
                progress_bar_analisis = st.progress(0, text="Iniciando Análisis...")
                for i, fila in df.iterrows():
                    prompt = construir_prompt_analisis(fila)
                    try:
                        response = model.generate_content(prompt)
                        texto_completo = response.text.strip()
                        # Separación robusta
                        header_que_evalua = "Qué Evalúa:"
                        header_correcta = "Ruta Cognitiva Correcta:"
                        header_distractores = "Análisis de Opciones No Válidas:"
                        idx_correcta = texto_completo.find(header_correcta)
                        idx_distractores = texto_completo.find(header_distractores)
                        que_evalua = texto_completo[len(header_que_evalua):idx_correcta].strip() if idx_correcta != -1 else texto_completo
                        just_correcta = texto_completo[idx_correcta:idx_distractores].strip() if idx_correcta != -1 and idx_distractores != -1 else (texto_completo[idx_correcta:].strip() if idx_correcta != -1 else "ERROR")
                        an_distractores = texto_completo[idx_distractores:].strip() if idx_distractores != -1 else "ERROR"
                    except Exception as e:
                        st.warning(f"Error en fila {i+1} (Análisis): {e}")
                        que_evalua, just_correcta, an_distractores = "ERROR API", "ERROR API", "ERROR API"
                    
                    que_evalua_lista.append(que_evalua)
                    just_correcta_lista.append(just_correcta)
                    an_distractores_lista.append(an_distractores)
                    progress_bar_analisis.progress((i + 1) / total_filas, text=f"Analizando Ítem {i+1}/{total_filas}")
                    time.sleep(1) # Control de velocidad de la API
                
                df["Que_Evalua"] = que_evalua_lista
                df["Justificacion_Correcta"] = just_correcta_lista
                df["Analisis_Distractores"] = an_distractores_lista
                st.success("Análisis de Ítems completado.")

            # Proceso de Recomendaciones
            with st.spinner("Generando Recomendaciones Pedagógicas... Esto también puede tardar."):
                fortalecer_lista, avanzar_lista = [], []
                progress_bar_recom = st.progress(0, text="Iniciando Recomendaciones...")
                for i, fila in df.iterrows():
                    prompt = construir_prompt_recomendaciones(fila)
                    try:
                        response = model.generate_content(prompt)
                        texto_completo = response.text.strip()
                        # Separación robusta
                        titulo_avanzar = "RECOMENDACIÓN PARA AVANZAR"
                        idx_avanzar = texto_completo.upper().find(titulo_avanzar)
                        if idx_avanzar != -1:
                            fortalecer = texto_completo[:idx_avanzar].strip()
                            avanzar = texto_completo[idx_avanzar:].strip()
                        else:
                            fortalecer, avanzar = texto_completo, "ERROR: No se encontró 'AVANZAR'"
                    except Exception as e:
                        st.warning(f"Error en fila {i+1} (Recomendaciones): {e}")
                        fortalecer, avanzar = "ERROR API", "ERROR API"
                    
                    fortalecer_lista.append(fortalecer)
                    avanzar_lista.append(avanzar)
                    progress_bar_recom.progress((i + 1) / total_filas, text=f"Generando Recomendación {i+1}/{total_filas}")
                    time.sleep(1) # Control de velocidad

                df["Recomendacion_Fortalecer"] = fortalecer_lista
                df["Recomendacion_Avanzar"] = avanzar_lista
                st.success("Recomendaciones generadas con éxito.")
            
            # Guardar el resultado en el estado de la sesión
            st.session_state.df_enriquecido = df
            st.balloons()

# --- PASO 3: Vista Previa y Verificación ---
if st.session_state.df_enriquecido is not None:
    st.header("Paso 3: Verifica los Datos Enriquecidos")
    st.dataframe(st.session_state.df_enriquecido.head())
    
    # Opción para descargar el Excel enriquecido
    output_excel = BytesIO()
    with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
        st.session_state.df_enriquecido.to_excel(writer, index=False, sheet_name='Datos Enriquecidos')
    output_excel.seek(0)
    
    st.download_button(
        label="📥 Descargar Excel Enriquecido",
        data=output_excel,
        file_name="excel_enriquecido_con_ia.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# --- PASO 4: Ensamblaje de Fichas ---
if st.session_state.df_enriquecido is not None:
    st.header("Paso 4: Ensambla las Fichas Técnicas")
    if not archivo_plantilla:
        st.warning("Por favor, sube una plantilla de Word para continuar con el ensamblaje.")
    else:
        columna_nombre_archivo = st.text_input(
            "Escribe el nombre de la columna para nombrar los archivos (ej. ItemId)", 
            value="ItemId"
        )
        
        if st.button("📄 Ensamblar Fichas Técnicas", type="primary"):
            df_final = st.session_state.df_enriquecido
            if columna_nombre_archivo not in df_final.columns:
                st.error(f"La columna '{columna_nombre_archivo}' no existe en el Excel. Por favor, elige una de: {', '.join(df_final.columns)}")
            else:
                with st.spinner("Ensamblando todas las fichas en un archivo .zip..."):
                    plantilla_bytes = BytesIO(archivo_plantilla.getvalue())
                    zip_buffer = BytesIO()
                    
                    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                        total_docs = len(df_final)
                        progress_bar_zip = st.progress(0, text="Iniciando ensamblaje...")
                        for i, fila in df_final.iterrows():
                            doc = DocxTemplate(plantilla_bytes)
                            contexto = fila.to_dict()
                            doc.render(contexto)
                            
                            doc_buffer = BytesIO()
                            doc.save(doc_buffer)
                            doc_buffer.seek(0)
                            
                            nombre_base = str(fila[columna_nombre_archivo]).replace('/', '_').replace('\\', '_')
                            nombre_archivo_salida = f"{nombre_base}.docx"
                            
                            zip_file.writestr(nombre_archivo_salida, doc_buffer.getvalue())
                            progress_bar_zip.progress((i + 1) / total_docs, text=f"Añadiendo ficha {i+1}/{total_docs} al .zip")
                    
                    st.session_state.zip_buffer = zip_buffer
                    st.success("¡Ensamblaje completado!")

# --- PASO 5: Descarga Final ---
if st.session_state.zip_buffer:
    st.header("Paso 5: Descarga el Resultado Final")
    st.download_button(
        label="📥 Descargar TODAS las fichas (.zip)",
        data=st.session_state.zip_buffer,
        file_name="fichas_tecnicas_generadas.zip",
        mime="application/zip"
    )
