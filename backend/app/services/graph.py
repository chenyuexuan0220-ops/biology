from collections import defaultdict
from sqlalchemy import select
from fastapi import HTTPException
from app.models import Edge


def validate_dag(edges):
    graph = defaultdict(list)
    for source, target in edges:
        graph[source].append(target)
    visiting, visited = set(), set()

    def visit(node):
        if node in visiting:
            raise ValueError("前置知识图不能包含循环")
        if node in visited:
            return
        visiting.add(node)
        for child in graph[node]:
            visit(child)
        visiting.remove(node)
        visited.add(node)

    for node in list(graph):
        visit(node)


def add_edge(db, payload):
    data = payload.model_dump(mode="json")
    if data["relation_type"] == "PREREQUISITE_OF":
        edges = [
            (e.source_knowledge_id, e.target_knowledge_id)
            for e in db.scalars(select(Edge).where(Edge.relation_type == "PREREQUISITE_OF"))
        ]
        try:
            validate_dag(edges + [(data["source_knowledge_id"], data["target_knowledge_id"])])
        except ValueError as exc:
            raise HTTPException(422, str(exc))
    edge = Edge(**data)
    db.add(edge)
    db.flush()
    return edge
