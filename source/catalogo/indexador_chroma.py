import hashlib

from catalogo.archivos_catalogo import leer_descripciones, leer_todos_los_recursos
from catalogo.base_vectorial import COLECCION_POR_TIPO, abrir_coleccion
from conexiones.modelo_embeddings import crear_modelo_embeddings


def armar_texto_para_embedding(recurso, descripcion):
    # Plantilla fija y general, el detalle de columnas va en extras
    return "\n".join([
        f"Tipo: {recurso['tipo']}",
        f"Titulo: {recurso.get('titulo', recurso['nombre'])}",
        f"Nombre: {recurso['nombre']}",
        f"Capa: {recurso.get('capa', '')} ({recurso.get('descripcion_capa', '')})",
        f"Descripcion: {descripcion['descripcion']}",
        f"Preguntas que responde: {' | '.join(descripcion['preguntas_que_responde'])}",
        f"Terminos de negocio: {', '.join(descripcion['terminos_de_negocio'])}",
    ])


def calcular_huella(texto):
    return hashlib.md5(texto.encode("utf-8")).hexdigest()


def indexar_recursos():
    recursos = leer_todos_los_recursos()
    descripciones = leer_descripciones()
    modelo_embeddings = crear_modelo_embeddings()

    for recurso in recursos:
        descripcion = descripciones.get(recurso["id"])
        if descripcion is None:
            print("Sin descripcion, se salta:", recurso["id"])
            continue

        coleccion = abrir_coleccion(COLECCION_POR_TIPO[recurso["tipo"]])
        texto = armar_texto_para_embedding(recurso, descripcion)
        huella = calcular_huella(texto)

        # Si el texto no cambio, no se vuelve a pedir el embedding
        existente = coleccion.get(ids=[recurso["id"]])
        if existente["ids"] and existente["metadatas"][0].get("huella") == huella:
            continue

        vector = modelo_embeddings.embed_documents([texto], titles=[recurso.get("titulo", recurso["nombre"])])[0]
        coleccion.upsert(
            ids=[recurso["id"]],
            embeddings=[vector],
            documents=[texto],
            metadatas=[{
                "nombre": recurso["nombre"],
                "titulo": recurso.get("titulo", recurso["nombre"]),
                "tipo": recurso["tipo"],
                "capa": recurso.get("capa", ""),
                "link": recurso.get("link", ""),
                "huella": huella,
            }],
        )
        print("Indexado:", recurso["id"])

    for nombre_coleccion in COLECCION_POR_TIPO.values():
        print(f"Coleccion {nombre_coleccion}: {abrir_coleccion(nombre_coleccion).count()} recursos")


if __name__ == "__main__":
    indexar_recursos()
