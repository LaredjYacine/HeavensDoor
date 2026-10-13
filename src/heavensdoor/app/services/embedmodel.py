from fastembed import TextEmbedding

_model = None


def get_embedding_model():
    global _model
    if _model is None:
        _model = TextEmbedding("BAAI/bge-small-en-v1.5")
    return _model
