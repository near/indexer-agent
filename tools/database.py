from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, ForeignKey, text
from sqlalchemy.exc import SQLAlchemyError
from langchain.tools import StructuredTool, tool

# import os

# # Locate PostgreSQL installation prefix
# postgres_prefix = os.popen("brew --prefix postgresql").read().strip()

# # Set environment variables
# os.environ['DYLD_FALLBACK_LIBRARY_PATH'] = f"{postgres_prefix}/lib:/usr/local/lib:/usr/lib"
# os.environ['PATH'] = f"{postgres_prefix}/bin:" + os.environ['PATH']
# os.environ['LDFLAGS'] = f"-L{postgres_prefix}/lib"
# os.environ['CPPFLAGS'] = f"-I{postgres_prefix}/include"
# os.environ['DYLD_LIBRARY_PATH'] = f"{postgres_prefix}/lib:" + os.environ.get('DYLD_LIBRARY_PATH', '')

# # Verify environment variables (optional, for debugging purposes)
# print(os.environ['DYLD_FALLBACK_LIBRARY_PATH'])
# print(os.environ['PATH'])
# print(os.environ['LDFLAGS'])
# print(os.environ['CPPFLAGS'])
# print(os.environ['DYLD_LIBRARY_PATH'])

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
