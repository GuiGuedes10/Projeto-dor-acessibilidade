"""Ciclo de vida do driver e execução de consultas de leitura."""
import atexit
import os
from Services.Neo4j.config import GraphConfigurationError, configured, username


class Neo4jConnection:
    def __init__(self, config, driver=None):
        self.config = config
        if driver is None:
            if not configured():
                raise GraphConfigurationError('Configure NEO4J_URI, NEO4J_USER e NEO4J_PASSWORD.')
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(os.environ['NEO4J_URI'],
                auth=(username(), os.environ['NEO4J_PASSWORD']),
                connection_timeout=5, max_transaction_retry_time=5)
            atexit.register(driver.close)
        self.driver = driver

    def read(self, statement, **parameters):
        from neo4j import Query
        records, _, _ = self.driver.execute_query(Query(statement, timeout=self.config.timeout),
            parameters_=parameters, database_=self.config.database, routing_='r')
        return [record.data() for record in records]
