from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, ForeignKey, text
from sqlalchemy.exc import SQLAlchemyError
from langchain.tools import StructuredTool, tool

def create_db_engine(db_name='db',user_name='username',password='password'):
    DATABASE_URI = f'postgresql://{user_name}:{password}@localhost:5432/{db_name}'
    try:
        # Create an engine and connect to the database
        engine = create_engine(DATABASE_URI)
        return engine
    except SQLAlchemyError as e:
        print(f"Failed to create engine: {e}. \n Go to README instructions on settting up Postgres locally:")
        return None

def run_sql(sql):
    engine = create_db_engine()
    sql = sql.replace("\\n", "").replace("\n","")
    sql_text = text(sql)
    try:
        with engine.connect() as connection:
            connection.execute(sql_text)
            return "DDL statement executed successfully."
    except SQLAlchemyError as e:
        return f"An error occurred running Postgresql: {e}"

@tool
def tool_run_sql_ddl(sql: str) -> str:
    """
    Tests running PostgreSQL DDL language, pass only the SQL DDL statement to run and remove any \n or \\n characters.

    Parameters:
    sql (str): SQL DDL statement to run.

    Returns:
    string: Success or error message.
    """    
    return run_sql(sql)
