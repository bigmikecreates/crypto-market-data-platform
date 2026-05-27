from fastapi import Request

from crypto_market_data_platform.query import QueryService


def get_query_service(request: Request) -> QueryService:
    return request.app.state.query_service
