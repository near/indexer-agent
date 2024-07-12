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

class DataUpsertionResponse(BaseModel):
    """Final DataUpsertion answer to the user"""

    data_upsertion_code: str = Field(description="The final javascript DataUpsertion code that user requested")
    explanation: str = Field(
        description="How did the agent come up with this answer?"
    )

DataUpsertion_parser = PydanticOutputParser(pydantic_object=DataUpsertionResponse)

def fetch_query_api_docs(directory):
    query_api_docs = ""
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".txt"):
                with open(os.path.join(root, file), 'r') as f:
                    query_api_docs += f.read()
    return query_api_docs.replace('{', '{{').replace('}', '}}')

def data_upsertion_code_model():
    # Define the prompt for the agent
    query_api_docs = fetch_query_api_docs('./query_api_docs')
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                '''
                You are a JavaScript software engineer working with NEAR Protocol. Your task is to write a pure JavaScript function 
                that accepts a JSON schema and PostgreSQL DDL, then generates Javascript for inserting data from the blockchain into the 
                specified table. Return only valid JavaScript code and use only standard JavaScript functions. Do not use Typescript. 

                The provided JavaScript function extracts relevant data from the blockchain block into the specificed schema. 
                Dynamically map the parsed blockchain data to the fields specified in the given PostgreSQL schema.
                Decode and parse the data as needed (e.g., base64 decoding).
                
                If you want to insert into a table `table_name`, instead use context.db.TableName.upsert as context.db functions must use PascalCase.
                Do not use a for loop to insert data. Instead, map the data variables and feed them into the upsert function.
                Prepare a list of objects to be upserted into the table and use a single async upsert command to insert all the data at once. 
                Avoid looping or mapping over the data array. Optimize the code so that it does not require extraneous queries. 
                
                Implement comprehensive error handling that includes retry logic for recoverable errors and specific responses for different error types.
                Validate and verify the existence of properties in data objects before using them. Implement fallbacks or error handling for missing properties to prevent runtime errors.
    
                Use async/await for database interactions to handle various types of blockchain data operations such as creation, 
                updating, and deleting records. Implement robust error handling for database operations. Log success and error messages for tracking purposes.
                Utilize near-lake primitives and context.db for upserts. Context is a global variable that contains helper methods, 
                including context.db for database interactions. The entire script should begin and end with an async function named getBlock.

                Output result in a DataUpsertionResponse format where 'DataUpsertion' field should have newlines (\\n) 
                replaced with their escaped version (\\\\n) to make the string valid for JavaScript.
                '''
            ),
            (
                "system",
                "Here is the documentation of how to use context.db methods to modify data in the table which you should use:" + query_api_docs,
            ),
            ( #one shot example
                "human",
                """
                Here is the relevant context code:
                    Postgresql schema: "CREATE TABLE block_results (
                        signer_id VARCHAR(255),
                        block_height INTEGER,
                        receipt_id VARCHAR(255) PRIMARY KEY,
                        block_datetime TIMESTAMP,
                        method_name VARCHAR(255),
                        task_ordinal INTEGER,
                        task_hash INTEGER[]
                    );"
                    Javascript Function: "return (function extractData(block) {
                        const results = [];
                        const actions = block.actions();
                        const receipts = block.receipts();
                        const header = block.header();
                        const height = header.height;
                        const datetime = new Date(parseInt(header.timestampNanosec) / 1e6);

                        actions
                            .filter(action => action.receiverId === 'app.nearcrowd.near')
                            .flatMap(action => {
                                const receipt = receipts.find(r => r.receiptId === action.receiptId);
                                if (receipt && receipt.status && receipt.status.SuccessValue !== undefined) {
                                    return action.operations
                                        .map(operation => operation.FunctionCall)
                                        .filter(operation => operation)
                                        .map(functionCallOperation => {
                                            try {
                                                const args = JSON.parse(Buffer.from(functionCallOperation.args, 'base64').toString('utf-8'));
                                                return {
                                                    signerId: action.signerId,
                                                    blockHeight: height,
                                                    receiptId: action.receiptId,
                                                    blockDatetime: datetime,
                                                    methodName: functionCallOperation.methodName,
                                                    ...args
                                                };
                                            } catch (error) {
                                                console.log('Failed to decode or parse function call args', functionCallOperation, error);
                                                return null;
                                            }
                                        })
                                        .filter(result => result !== null);
                                }
                                return [];
                            })
                            .forEach(result => results.push(result));

                        return results;
                    })(block);"
                    Entity Schema: "{
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                            "signerId": {
                                "type": "string"
                            },
                            "blockHeight": {
                                "type": "integer"
                            },
                            "receiptId": {
                                "type": "string"
                            },
                            "blockDatetime": {
                                "type": "string"
                            },
                            "methodName": {
                                "type": "string"
                            },
                            "task_ordinal": {
                                "type": "integer"
                            },
                            "task_hash": {
                                "type": "array",
                                "items": {
                                "type": "integer"
                                }
                            }
                            },
                            "required": [
                            "blockDatetime",
                            "blockHeight",
                            "methodName",
                            "receiptId",
                            "signerId",
                            "task_hash",
                            "task_ordinal"
                            ]
                        }
                    }"
                """.replace('{','{{').replace('}','}}')
            ),
            (
                "ai",
                """
                `import * as primitives from "@near-lake/primitives";
                async function getBlock(block: primitives.Block) {
                    async function extractData(block) {
                        const results = [];
                        try {
                            const actions = block.actions();
                            const receipts = block.receipts();
                            const header = block.header();
                            const height = header.height;
                            const datetime = new Date(parseInt(header.timestampNanosec) / 1e6);

                            actions
                                .filter(action => action.receiverId === 'app.nearcrowd.near')
                                .flatMap(action => {
                                    try {
                                        const receipt = receipts.find(r => r.receiptId === action.receiptId);
                                        if (receipt && receipt.status && receipt.status.SuccessValue !== undefined) {
                                            return action.operations
                                                .map(operation => operation.FunctionCall)
                                                .filter(operation => operation)
                                                .map(functionCallOperation => {
                                                    try {
                                                        const args = JSON.parse(Buffer.from(functionCallOperation.args, 'base64').toString('utf-8'));
                                                        return {
                                                            signerId: action.signerId,
                                                            blockHeight: height,
                                                            receiptId: action.receiptId,
                                                            blockDatetime: datetime,
                                                            methodName: functionCallOperation.methodName,
                                                            ...args
                                                        };
                                                    } catch (error) {
                                                        console.log('Failed to decode or parse function call args', functionCallOperation, error);
                                                        return null;
                                                    }
                                                })
                                                .filter(result => result !== null);
                                        }
                                    } catch (error) {
                                        console.error("Error processing action:", error);
                                        return [];
                                    }
                                    return [];
                                })
                                .forEach(result => results.push(result));
                        } catch (error) {
                            console.error("Error extracting data:", error);
                        }

                        return results;
                    }

                    try {
                        const results = await extractData(block);
                        try {
                            await context.db.BlockResults.upsert(
                                results,
                                ["receipt_id"],
                                [
                                    "signer_id",
                                    "block_height",
                                    "block_datetime",
                                    "method_name",
                                    "task_ordinal",
                                    "task_hash",
                                ]
                            );
                            console.log("Data upserted successfully");
                        } catch (error) {
                            console.error("Error upserting data:", error);
                        }
                    } catch (error) {
                        console.error("Error calling extractData:", error);
                    }
                }`
                explanation: "Defines an asynchronous function getBlock that processes a given block from the Near blockchain. 
                It extracts relevant data from actions targeted at the app.nearcrowd.near account, including decoding arguments from base64 to JSON.
                For each action that successfully completes (indicated by a successful receipt status), it constructs an object containing details 
                such as the signer ID, block height, receipt ID, block timestamp, and method name, along with the decoded arguments. 
                These objects are then attempted to be upserted into a database with specified fields for conflict resolution and data insertion. 
                The process includes error handling at multiple stages to log issues encountered during data extraction or database upsertion."
                """.replace('{','{{').replace('}','}}')
            ),
            ( #few shot example with NEAR Social
                "human",
                """Here is the relevant context code:
                Postgresql schema: `CREATE TABLE
                "posts" (
                    "id" SERIAL NOT NULL,
                    "account_id" VARCHAR NOT NULL,
                    "block_height" DECIMAL(58, 0) NOT NULL,
                    "receipt_id" VARCHAR NOT NULL,
                    "content" TEXT NOT NULL,
                    "block_timestamp" DECIMAL(20, 0) NOT NULL,
                    "accounts_liked" JSONB NOT NULL DEFAULT '[]',
                    "last_comment_timestamp" DECIMAL(20, 0),
                    CONSTRAINT "posts_pkey" PRIMARY KEY ("id")
                );

                CREATE TABLE
                "comments" (
                    "id" SERIAL NOT NULL,
                    "post_id" SERIAL NOT NULL,
                    "account_id" VARCHAR NOT NULL,
                    "block_height" DECIMAL(58, 0) NOT NULL,
                    "content" TEXT NOT NULL,
                    "block_timestamp" DECIMAL(20, 0) NOT NULL,
                    "receipt_id" VARCHAR NOT NULL,
                    CONSTRAINT "comments_pkey" PRIMARY KEY ("id")
                );

                CREATE TABLE
                "post_likes" (
                    "post_id" SERIAL NOT NULL,
                    "account_id" VARCHAR NOT NULL,
                    "block_height" DECIMAL(58, 0),
                    "block_timestamp" DECIMAL(20, 0) NOT NULL,
                    "receipt_id" VARCHAR NOT NULL,
                    CONSTRAINT "post_likes_pkey" PRIMARY KEY ("post_id", "account_id")
                );

                CREATE UNIQUE INDEX "posts_account_id_block_height_key" ON "posts" ("account_id" ASC, "block_height" ASC);

                CREATE UNIQUE INDEX "comments_post_id_account_id_block_height_key" ON "comments" (
                "post_id" ASC,
                "account_id" ASC,
                "block_height" ASC
                );

                CREATE INDEX
                "posts_last_comment_timestamp_idx" ON "posts" ("last_comment_timestamp" DESC);

                ALTER TABLE
                "comments"
                ADD
                CONSTRAINT "comments_post_id_fkey" FOREIGN KEY ("post_id") REFERENCES "posts" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

                ALTER TABLE
                "post_likes"
                ADD
                CONSTRAINT "post_likes_post_id_fkey" FOREIGN KEY ("post_id") REFERENCES "posts" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;`
                Javascript Function: `const SOCIAL_DB = "social.near";
                function base64decode(encodedValue) {
                let buff = Buffer.from(encodedValue, "base64");
                return JSON.parse(buff.toString("utf-8"));
                }

                const nearSocialPosts = block
                .actions()
                .filter((action) => action.receiverId === SOCIAL_DB)
                .flatMap((action) =>
                    action.operations
                    .map((operation) => operation["FunctionCall"])
                    .filter((operation) => operation?.methodName === "set")
                    .map((functionCallOperation) => {
                        try {
                        const decodedArgs = base64decode(functionCallOperation.args);
                        return {
                            accountId: Object.keys(decodedArgs.data)[0],
                            data: decodedArgs.data[Object.keys(decodedArgs.data)[0]]
                        };
                        } catch (error) {
                        console.log("Failed to decode function call args", functionCallOperation, error);
                        }
                    })
                );

                return nearSocialPosts;`
                Entity Schema: 
                `{
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                        "accountId": {
                            "type": "string"
                        },
                        "data": {
                            "type": "object",
                            "properties": {
                            "index": {
                                "type": "object",
                                "properties": {
                                "cheddarChatterComment-v0.0.1": {
                                    "type": "string"
                                },
                                "notify": {
                                    "type": "string"
                                }
                                },
                                "required": [
                                "cheddarChatterComment-v0.0.1",
                                "notify"
                                ]
                            },
                            "post": {
                                "type": "object",
                                "properties": {
                                "main": {
                                    "type": "string"
                                }
                                },
                                "required": [
                                "main"
                                ]
                            }
                            },
                            "required": [
                            "index",
                            "post"
                            ]
                        }
                        },
                        "required": [
                        "accountId",
                        "data"
                        ]
                    }
                }`
                """.replace('{','{{').replace('}','}}'),
            ),
            (
                "ai",
                """
                data_upsertion_code: 
                `import * as primitives from "@near-lake/primitives";
                async function getBlock(block: primitives.Block) {
                    const SOCIAL_DB = "social.near";
                    function base64decode(encodedValue) {
                        let buff = Buffer.from(encodedValue, "base64");
                        return JSON.parse(buff.toString("utf-8"));
                    }
                    const nearSocialPosts = block
                        .actions()
                        .filter((action) => action.receiverId === SOCIAL_DB)
                        .flatMap((action) =>
                        action.operations
                            .map((operation) => operation["FunctionCall"])
                            .filter((operation) => operation?.methodName === "set")
                            .map((functionCallOperation) => {
                            try {
                                const decodedArgs = base64decode(functionCallOperation.args);
                                return {
                                ...functionCallOperation,
                                args: decodedArgs,
                                receiptId: action.receiptId,
                                };
                            } catch (error) {
                                console.log(
                                "Failed to decode function call args",
                                functionCallOperation,
                                error
                                );
                            }
                            })
                            .filter((functionCall) => {
                            try {
                                const accountId = Object.keys(functionCall.args.data)[0];
                                return (
                                Object.keys(functionCall.args.data[accountId]).includes("post") ||
                                Object.keys(functionCall.args.data[accountId]).includes("index")
                                );
                            } catch (error) {
                                console.log(
                                "Failed to parse decoded function call",
                                functionCall,
                                error
                                );
                            }
                            })
                        );
                    if (nearSocialPosts.length > 0) {
                    console.log("Found Near Social Posts in Block...");
                    const blockHeight = block.blockHeight;
                    const blockTimestamp = block.header().timestampNanosec;
                    await Promise.all(
                    nearSocialPosts.map(async (postAction) => {
                        const accountId = Object.keys(postAction.args.data)[0];
                        console.log(`ACCOUNT_ID: ${accountId}`);

                        // if creates a post
                        if (
                        postAction.args.data[accountId].post &&
                        Object.keys(postAction.args.data[accountId].post).includes("main")
                        ) {
                        console.log("Creating a post...");
                        await handlePostCreation(
                            ... // arguments required for handlePostCreation
                        );
                        } else if (
                        postAction.args.data[accountId].post &&
                        Object.keys(postAction.args.data[accountId].post).includes("comment")
                        ) {
                        // if creates a comment
                        await handleCommentCreation(
                            ... // arguments required for handleCommentCreation
                        );
                        } else if (
                        Object.keys(postAction.args.data[accountId]).includes("index")
                        ) {
                        // Probably like or unlike action is happening
                        if (
                            Object.keys(postAction.args.data[accountId].index).includes("like")
                        ) {
                            console.log("handling like");
                            await handleLike(
                            ... // arguments required for handleLike
                            );
                        }
                        }
                    })
                    );
                }
                async function handlePostCreation(
                    accountId,
                    blockHeight,
                    blockTimestamp,
                    receiptId,
                    content
                ) {
                    try {
                    const postData = {
                        account_id: accountId,
                        block_height: blockHeight,
                        block_timestamp: blockTimestamp,
                        content: content,
                        receipt_id: receiptId,
                    };

                    // Call GraphQL mutation to insert a new post
                    await context.db.Posts.insert(postData);

                    console.log(`Post by ${accountId} has been added to the database`);
                    } catch (e) {
                    console.log(
                        `Failed to store post by ${accountId} to the database (perhaps it is already stored)`
                    );
                    }
                }
                async function handleCommentCreation(
                    accountId,
                    blockHeight,
                    blockTimestamp,
                    receiptId,
                    commentString
                ) {
                    try {
                    const comment = JSON.parse(commentString);
                    const postAuthor = comment.item.path.split("/")[0];
                    const postBlockHeight = comment.item.blockHeight;

                    // find post to retrieve Id or print a warning that we don't have it
                    try {
                        // Call GraphQL query to fetch posts that match specified criteria
                        const posts = await context.db.Posts.select(
                        { account_id: postAuthor, block_height: postBlockHeight },
                        1
                        );
                        console.log(`posts: ${JSON.stringify(posts)}`);
                        if (posts.length === 0) {
                        return;
                        }

                        const post = posts[0];

                        try {
                        delete comment["item"];
                        const commentData = {
                            account_id: accountId,
                            receipt_id: receiptId,
                            block_height: blockHeight,
                            block_timestamp: blockTimestamp,
                            content: JSON.stringify(comment),
                            post_id: post.id,
                        };
                        // Call GraphQL mutation to insert a new comment
                        await context.db.Comments.insert(commentData);

                        // Update last comment timestamp in Post table
                        const currentTimestamp = Date.now();
                        await context.db.Posts.update(
                            { id: post.id },
                            { last_comment_timestamp: currentTimestamp }
                        );
                        console.log(`Comment by ${accountId} has been added to the database`);
                        } catch (e) {
                        console.log(
                            `Failed to store comment to the post ${postAuthor}/${postBlockHeight} by ${accountId} perhaps it has already been stored. Error ${e}`
                        );
                        }
                    } catch (e) {
                        console.log(
                        `Failed to store comment to the post ${postAuthor}/${postBlockHeight} as we don't have the post stored.`
                        );
                    }
                    } catch (error) {
                    console.log("Failed to parse comment content. Skipping...", error);
                    }
                }
                async function handleLike(
                    accountId,
                    blockHeight,
                    blockTimestamp,
                    receiptId,
                    likeContent
                ) {
                    try {
                    const like = JSON.parse(likeContent);
                    const likeAction = like.value.type; // like or unlike
                    const [itemAuthor, _, itemType] = like.key.path.split("/", 3);
                    const itemBlockHeight = like.key.blockHeight;
                    console.log("handling like", receiptId, accountId);
                    switch (itemType) {
                        case "main":
                        try {
                            const posts = await context.db.Posts.select(
                            { account_id: itemAuthor, block_height: itemBlockHeight },
                            1
                            );
                            if (posts.length == 0) {
                            return;
                            }

                            const post = posts[0];
                            switch (likeAction) {
                            case "like":
                                await _handlePostLike(
                                post.id,
                                accountId,
                                blockHeight,
                                blockTimestamp,
                                receiptId
                                );
                                break;
                            case "unlike":
                                await _handlePostUnlike(post.id, accountId);
                                break;
                            }
                        } catch (e) {
                            console.log(
                            `Failed to store like to post ${itemAuthor}/${itemBlockHeight} as we don't have it stored in the first place.`
                            );
                        }
                        break;
                        case "comment":
                        // Comment
                        console.log(`Likes to comments are not supported yet. Skipping`);
                        break;
                        default:
                        // something else
                        console.log(`Got unsupported like type "${itemType}". Skipping...`);
                        break;
                    }
                    } catch (error) {
                    console.log("Failed to parse like content. Skipping...", error);
                    }
                }
                async function _handlePostLike(
                    postId,
                    likeAuthorAccountId,
                    likeBlockHeight,
                    blockTimestamp,
                    receiptId
                ) {
                    try {
                    const posts = await context.db.Posts.select({ id: postId });
                    if (posts.length == 0) {
                        return;
                    }
                    const post = posts[0];
                    let accountsLiked =
                        post.accounts_liked.length === 0
                        ? post.accounts_liked
                        : JSON.parse(post.accounts_liked);

                    if (accountsLiked.indexOf(likeAuthorAccountId) === -1) {
                        accountsLiked.push(likeAuthorAccountId);
                    }

                    // Call GraphQL mutation to update a post's liked accounts list
                    await context.db.Posts.update(
                        { id: postId },
                        { accounts_liked: JSON.stringify(accountsLiked) }
                    );

                    const postLikeData = {
                        post_id: postId,
                        account_id: likeAuthorAccountId,
                        block_height: likeBlockHeight,
                        block_timestamp: blockTimestamp,
                        receipt_id: receiptId,
                    };
                    // Call GraphQL mutation to insert a new like for a post
                    await context.db.PostLikes.insert(postLikeData);
                    } catch (e) {
                    console.log(`Failed to store like to in the database: ${e}`);
                    }
                }
                async function _handlePostUnlike(postId, likeAuthorAccountId) {
                    try {
                    const posts = await context.db.Posts.select({ id: postId });
                    if (posts.length == 0) {
                        return;
                    }
                    const post = posts[0];
                    let accountsLiked =
                        post.accounts_liked.length === 0
                        ? post.accounts_liked
                        : JSON.parse(post.accounts_liked);

                    console.log(accountsLiked);

                    let indexOfLikeAuthorAccountIdInPost =
                        accountsLiked.indexOf(likeAuthorAccountId);
                    if (indexOfLikeAuthorAccountIdInPost > -1) {
                        accountsLiked.splice(indexOfLikeAuthorAccountIdInPost, 1);
                        // Call GraphQL mutation to update a post's liked accounts list
                        await context.db.Posts.update(
                        { id: postId },
                        { accounts_liked: JSON.stringify(accountsLiked) }
                        );
                    }
                    // Call GraphQL mutation to delete a like for a post
                    await context.db.PostLikes.delete({
                        account_id: likeAuthorAccountId,
                        post_id: postId,
                    });
                    } catch (e) {
                    console.log(`Failed to delete like from the database: ${e}`);
                    }
                }
                };`
                explanation: "The function can be explained in two parts. The first filters relevant transactional data for processing by the helper functions defined earlier in the file scope, the second part uses the helper functions to ultimately save the relevant data to for querying by applications.
                We first designate the near account ID that is on the receiving end of the transactions picked up by the indexer, as SOCIAL_DB = "social.near" and later with the equality operator for this check. This way we only filter for transactions that are relevant to the social.near account ID for saving data on-chain.
                The filtering logic then begins by calling block.actions() where block is defined within the @near-lake/primtives package. The output from this filtering is saved in a nearSocialPosts variable for later use by the helper functions. The .filter() line helps specify for transactions exclusively that have interacted with the SocialDB. .flatMap() specifies the types of transaction and looks for attributes in the transaction data on which to base the filter.
                Specifically, .flatMap() filters for FunctionCall call types, calling the set method of the SocialDB contract. In addition, we look for transactions that include a receiptId and include either post or index in the function call argument data.
                This logic is only entered if there are any nearSocialPosts, in which case it first declares the blockHeight and blockTimestamp variables that will be relevant when handling (transforming and persisting) the data. Then the processing for every transaction (or function call) is chained as a promise for asynchronous execution.
                Within every promise, the accountId performing the call is extracted from the transaction data first. Then, depending on the attributes in the transaction data, there is logic for handling post creation, comment creation, or a like/unlike."
                """.replace('{','{{').replace('}','}}'),
            ),         
            MessagesPlaceholder(variable_name="messages", optional=True),
        ]
    ).partial(format_instructions=DataUpsertion_parser.get_format_instructions())

    # Create the OpenAI LLM
    llm = ChatOpenAI(model="gpt-4o", temperature=0, streaming=True,)

    model = {"messages": RunnablePassthrough()} | prompt | llm.with_structured_output(DataUpsertionResponse) #.bind_tools(tools)
    return model

# Define a class for handling the generation of data upsertion code
class DataUpsertionCodeAgent:
    def __init__(self, model):
        # Initialize the agent with a model for generating code
        self.model = model

    def call_model(self, state):
        # Start the process of generating data upsertion code
        print("Generating Data Upsertion Code")
        
        # Retrieve necessary information from the state
        messages = state.messages  # All messages exchanged in the process
        table_creation_code = state.table_creation_code  # SQL code for creating tables
        data_upsertion_code = state.data_upsertion_code  # Current data upsertion code (if any)
        block_data_extraction_code = state.block_data_extraction_code  # JavaScript code for extracting block data
        entity_schema = state.entity_schema  # Schema of the block data
        iterations = state.iterations  # Number of iterations the process has gone through
        
        # On the first iteration, append a message with relevant context for the model
        if iterations == 0:  # Check if it's the first iteration
            upsert_messages = [messages[0]]  # only take the original message
            upsert_messages.append(HumanMessage(content=f"""Here is the relevant context code:
            Postgresql schema: {table_creation_code}
            Javascript Function: {block_data_extraction_code}
            Entity Schema: {entity_schema}"""))
        else:
            upsert_messages = messages[(-1-iterations*2):]

        # Invoke the model with the current messages to generate/update the data upsertion code
        response = self.model.invoke(upsert_messages)
        # Wrap the response in a system message for logging or further processing
        wrapped_message = SystemMessage(content=str(response))
        # Update the data upsertion code with the response from the model
        data_upsertion_code = response.data_upsertion_code

        # Return the updated state including the new data upsertion code and incremented iteration count
        return {"messages": messages + [wrapped_message], "data_upsertion_code": data_upsertion_code, "should_continue": False, "iterations": iterations + 1}