import os
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from langchain_community.graphs import Neo4jGraph

from langchain_neo4j import GraphCypherQAChain
def setup_retrieval(neo4j_url, neo4j_username, neo4j_password):
    """Initialize Neo4j connection and set up the QA retrieval chain."""
    
    load_dotenv()
    
    # Initialize embeddings and LLM
    embeddings = OpenAIEmbeddings()
    key="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"
    llm = ChatOpenAI(model_name="gpt-4o",api_key=key)
    
    # Connect to Neo4j graph
    graph = Neo4jGraph(
        url=neo4j_url,
        username=neo4j_username,
        password=neo4j_password
    )
    
   
    
    # Retrieve the graph schema (call if it's callable)
    try:
        schema = graph.get_schema()
    except TypeError:
        schema = graph.get_schema
    
    
    # Set up the QA chain
    template = """
Task: Generate a Cypher statement to query the graph database.

Instructions:
Use only relationship types and properties provided in schema.
Do not use other relationship types or properties that are not provided.

schema:
{schema}

Note: Do not include explanations or apologies in your answers.
Do not answer questions that ask anything other than creating Cypher statements.
Do not include any text other than generated Cypher statements.

Question: {question}"""
    
    question_prompt = PromptTemplate(
        template=template,
        input_variables=["schema", "question"]
    )
    
    qa = GraphCypherQAChain.from_llm(
        llm=llm,
        graph=graph,
        cypher_prompt=question_prompt,
        verbose=True,
        allow_dangerous_requests=True
    )
    
    return qa

def ask_question(qa, question):
    """Ask a question using the QA chain and return the result."""
    result = qa.invoke({"query": question})
    return result.get('result', 'No result returned')

def main():
    # Configuration
    NEO4J_URL = os.getenv("NEO4J_URL", "neo4j+s://e5c7fa42.databases.neo4j.io")
    NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "xR15egCk9mX8Tf4Xo1Wf_Z355rINJ7iO-uyZyx_1T8k")
    
    print("Initializing retrieval chain...")
    qa = setup_retrieval(NEO4J_URL, NEO4J_USERNAME, NEO4J_PASSWORD)
    # `qa.graph.get_schema` may be a callable or a cached string; handle both.
    schema_attr = qa.graph.get_schema
    if callable(schema_attr):
        print(schema_attr())
    else:
        print(schema_attr)
    print("Ready for queries.\n")
    
    # Interactive question loop
    while True:
        question = input("Enter your question (or 'quit' to exit): ").strip()
        if question.lower() == 'quit':
            break
        if question:
            print("\nGenerating answer...")
            answer = ask_question(qa, question)
            print(f"Answer: {answer}\n")

if __name__ == "__main__":
    main()


