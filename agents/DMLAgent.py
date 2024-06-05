# Define the response schema for our agent
import json
import os
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.utils.function_calling import convert_to_openai_function
from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langgraph.prebuilt import ToolExecutor,ToolInvocation
from langchain_core.messages import ToolMessage,SystemMessage,HumanMessage
from langchain.output_parsers import PydanticOutputParser

class DMLResponse(BaseModel):
    """Final DML answer to the user"""

    dml: str = Field(description="The final javascript DML code that user requested")
    explanation: str = Field(
        description="How did the agent come up with this answer?"
    )

dml_parser = PydanticOutputParser(pydantic_object=DMLResponse)

def fetch_query_api_docs(directory):
    query_api_docs = ""
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".txt"):
                with open(os.path.join(root, file), 'r') as f:
                    query_api_docs += f.read()
    return query_api_docs.replace('{', '{{').replace('}', '}}')

def dml_code_model(tools):
    query_api_docs = fetch_query_api_docs('./query-api-docs')
    # Define the prompt for the agent
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                '''
                You are a JavaScript software engineer working with NEAR Protocol. Your task is to write a pure JavaScript function 
                that accepts a JSON schema and PostgreSQL DDL, then generates DML for inserting data from the blockchain into the 
                specified table.

                Output result in a DMLResponse format where 'dml' field should have newlines (\\n) 
                replaced with their escaped version (\\\\n) to make the string valid for JavaScript.

                Requirements:

                Standard JavaScript Only:
                - Do not use TypeScript.
                - Use only standard JavaScript functions.
                Parse Blockchain Data:
                - Use the provided JavaScript function to extract relevant data from the blockchain block.
                - Decode and parse the data as needed (e.g., base64 decoding).
                Data Mapping and Upserting:
                - Dynamically map the parsed blockchain data to the fields specified in the given PostgreSQL schema.
                - Use async/await for database interactions.
                - Handle various types of blockchain data operations such as creation, updating, and deleting records.
                Error Handling and Logging:
                - Implement robust error handling for database operations.
                - Log success and error messages for tracking purposes.
                NEAR Primitives and Context:
                - Begin the script with: import * as primitives from "@near-lake/primitives";
                - Utilize near-lake primitives and context.db for upserts.
                - getBlock(block, context) applies your custom logic to a Block on Near and commits the data to a database.
                - context is a global variable that contains helper methods, including context.db for database interactions.
                ''',
            ),
            (
            "system",
            "Here is the documentation of how to build an indexer to help you plan:" + query_api_docs,
            ),
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    ).partial(format_instructions=dml_parser.get_format_instructions())

    # Create the OpenAI LLM
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, streaming=True,)

    # Create the tools to bind to the model
    tools = [convert_to_openai_function(t) for t in tools]

    model = {"messages": RunnablePassthrough()} | prompt | llm.with_structured_output(DMLResponse) #.bind_tools(tools)
    return model

def dml_code_model_v2(tools):
    # Define the prompt for the agent
    one_shot = """
            Here is an example of a SQL schema and it's corresponding DML code:
            SQL Schema:
            CREATE TABLE "aurora_claims" (
                "id" SERIAL NOT NULL,
                "token_id" VARCHAR NOT NULL,
                "block_height" DECIMAL(58, 0) NOT NULL,
                "receipt_id" VARCHAR NOT NULL,
                "block_timestamp" DECIMAL(20, 0) NOT NULL,
                CONSTRAINT "claims_pkey" PRIMARY KEY ("id")
            );

            Javascript Code:
            import * as primitives from "@near-lake/primitives";
            async function getBlock(block: primitives.Block) {
            function base64decode(encodedValue) {
                let buff = Buffer.from(encodedValue, "base64");
                return JSON.parse(buff.toString("utf-8"));
            }

            async function handleClaims(tokenId, blockHeight, blockTimestamp, receiptId) {
                try {
                const claimData = {
                    token_id: tokenId,
                    block_height: blockHeight,
                    block_timestamp: blockTimestamp,
                    receipt_id: receiptId,
                };

                // Call GraphQL mutation to insert a new post
                await context.db.AuroraClaims.insert(claimData);

                console.log(`Claim for ${tokenId} has been added to the database`);
                } catch (e) {
                console.log(
                    `Failed to store claim of ${tokenId} to the database (perhaps it is already stored)`
                );
                }
            }

            const AURORA_CLAIMS = "aurora.pool.near";

            let auroraClaims = [];
            try {
                const actions = block.actions();
                if (!actions) {
                console.log("Block has no actions");
                return;
                }
                const aurora_Actions = actions.filter(
                (action) => action.receiverId === AURORA_CLAIMS
                );
                if (!aurora_Actions) {
                console.log("Block has no Aurora actions");
                return;
                }
                auroraClaims = aurora_Actions.flatMap((action) =>
                action.operations
                    .map((operation) => operation["FunctionCall"])
                    .filter((operation) => operation?.methodName === "claim")
                    .map((functionCallOperation) => {
                    try {
                        return {
                        ...functionCallOperation,
                        args: base64decode(functionCallOperation.args),
                        receiptId: action.receiptId, // providing receiptId as we need it
                        };
                    } catch (e) {
                        console.log("Error parsing function call", e);
                    }
                    })
                    .filter((functionCall) => {
                    try {
                        if (
                        !functionCall ||
                        !functionCall.args ||
                        !functionCall.args.token_id
                        ) {
                        console.log(
                            "Set operation did not have arg data in expected format"
                        );
                        return;
                        }
                        const tokenId = functionCall.args.token_id;
                        return functionCall.args.token_id;
                    } catch (e) {
                        console.log("Error parsing aurora claims", functionCall);
                    }
                    })
                );
            } catch (e) {
                console.log("Error parsing aurora operations", block.actions());
            }

            if (auroraClaims.length > 0) {
                console.log("Found Aurora Claims in Block...");
                const blockHeight = block.blockHeight;
                const blockTimestamp = block.header().timestampNanosec;
                await Promise.all(
                auroraClaims.map(async (claimAction) => {
                    const tokenId = claimAction.args.token_id;
                    console.log(`TOKEN_ID: ${tokenId}`);

                    // if creates a claim
                    if (tokenId) {
                    console.log("Creating a claim...");
                    await handleClaims(
                        tokenId,
                        blockHeight,
                        blockTimestamp,
                        claimAction.receiptId
                    );
                    }
                })
                );
            }
            }

            """

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                '''
                You are a JavaScript software engineer working with NEAR Protocol. Your task is to write a pure JavaScript function 
                that accepts a JSON schema and PostgreSQL DDL, then generates DML for inserting data from the blockchain into the 
                specified table.

                Output result in a DMLResponse format where 'dml' field should have newlines (\\n) 
                replaced with their escaped version (\\\\n) to make the string valid for JavaScript.
                '''
            ),
            (
            "system",one_shot.replace('\n', '\\n').replace('{', '{{').replace('}', '}}')
            ),
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    ).partial(format_instructions=dml_parser.get_format_instructions())

    # Create the OpenAI LLM
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, streaming=True,)

    # Create the tools to bind to the model
    tools = [convert_to_openai_function(t) for t in tools]

    model = {"messages": RunnablePassthrough()} | prompt | llm.with_structured_output(DMLResponse) #.bind_tools(tools)
    return model

class DMLCodeAgent:
    def __init__(self, model, tool_executor: ToolExecutor):
        self.model = model
        self.tool_executor = tool_executor

    def call_model(self, state):
        messages = state['messages']
        dml_code = state['dml_code']
        iterations = state['iterations']
        response = self.model.invoke(messages)
        wrapped_message = SystemMessage(content=str(response))
        dml_code = response.dml
        return {"messages": messages + [wrapped_message],"dml_code": dml_code, "should_continue": False,"iterations":iterations+1}
    
    def human_review(self,state):
        messages = state["messages"]
        # last_tool_call = messages[-2]
        # get_block_schema_call =  last_tool_call.additional_kwargs["tool_calls"][0]["function"]["arguments"]
        dml_code = state["dml_code"]
        error = state["error"]
        response=""
        while response != "yes" or response != "no":
            response = input(prompt=f"Please review the DML code: {dml_code}. Is it correct? (yes/no)")
            if response == "yes":
                return {"messages": messages, "should_continue": True}
            elif response == "no":
                feedback = input(f"Please provide feedback on the DML code: {dml_code}")
                return {"messages": messages + [HumanMessage(content=feedback)], "should_continue": False}