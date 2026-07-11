from lingjing_ai.api.app import create_app
from lingjing_ai.api.bootstrap import build_default_pipeline


app = create_app(build_default_pipeline())
