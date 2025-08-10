import os

class Config:
    """
    Simple configuration loader.  This class reads environment variables
    for the various external API keys and endpoints required by the
    service.  If an environment variable is not provided it will
    default to None.  You can override these values at runtime by
    defining the environment variables before starting the service.
    """
    TRONSCAN_API_KEY: str = os.getenv("TRONSCAN_API_KEY")
    QUICKNODE_API_URL: str = os.getenv("QUICKNODE_API_URL")
    ALCHEMY_API_KEY: str = os.getenv("ALCHEMY_API_KEY", "")
