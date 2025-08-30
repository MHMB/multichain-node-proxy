from fastapi.middleware.cors import CORSMiddleware

def get_cors_middleware():
    """Get CORS middleware configuration."""
    return CORSMiddleware(
        allow_origins=["*"],  # Configure this appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
