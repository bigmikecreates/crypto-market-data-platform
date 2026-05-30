from fastapi import Request

from cmpd.query import QueryService


def get_query_service(request: Request) -> QueryService:
    return request.app.state.query_service
