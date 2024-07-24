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
                
                If you want to upsert into a table `table_name`, instead use context.db.TableName.upsert as context.db functions must use PascalCase.
                Do not use a for loop to insert data. Instead, map the data variables and feed them into the upsert function.
                Prepare a list of objects to be upserted into the table and use a single async upsert command to insert all the data at once. 
                Avoid looping or mapping over the data array. Optimize the code so that it does not require extraneous queries. 
                
                Implement VERY comprehensive error handling that includes retry logic for recoverable errors and specific responses for different error types.
                Validate and verify the existence of properties in data objects before using them. Also include fallbacks or error handling for missing properties to prevent runtime errors.
    
                Use async/await for database interactions to handle various types of blockchain data operations such as creation, 
                updating, and deleting records. Implement robust error handling for database operations. Log success and error messages for tracking purposes.
                Utilize near-lake primitives and context.db for upserts. Context is a global variable that contains helper methods, 
                including context.db for database interactions. For EACH table, there should be a corresponding context.db action. 
                The entire script should begin and end with an async function named getBlock.

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
                "data_upsertion_code": `import * as primitives from "@near-lake/primitives";
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
                }`,
                "explanation": "Defines an asynchronous function getBlock that processes a given block from the Near blockchain. 
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
                Postgresql schema: `CREATE TABLE "posts" (
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

                CREATE TABLE
                "promote" (
                    "id" SERIAL NOT NULL,
                    "account_id" VARCHAR NOT NULL,
                    "receipt_id" VARCHAR NOT NULL,
                    "block_height" DECIMAL(58, 0) NOT NULL,
                    "block_timestamp" DECIMAL(20, 0) NOT NULL,
                    "promotion_type" TEXT NOT NULL,
                    "post_id" SERIAL NOT NULL
                );

                CREATE TABLE
                "reposts" (
                    "id" SERIAL NOT NULL,
                    "post_id" SERIAL NOT NULL,
                    "account_id" VARCHAR NOT NULL,
                    "content" TEXT NOT NULL,
                    "block_height" DECIMAL(58, 0) NOT NULL,
                    "block_timestamp" DECIMAL(20, 0) NOT NULL,
                    "receipt_id" VARCHAR NOT NULL,
                    CONSTRAINT "reposts_pkey" PRIMARY KEY ("post_id", "account_id")
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
                Entity Schema: `{
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
                "data_upsertion_code": `import * as primitives from "@near-lake/primitives";
                async function getBlock(block: primitives.Block) {
                function base64decode(encodedValue) {
                    let buff = Buffer.from(encodedValue, "base64");
                    return JSON.parse(buff.toString("utf-8"));
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

                async function handlePromotion(
                    accountId,
                    blockHeight,
                    blockTimestamp,
                    receiptId,
                    promoteString
                ) {
                    const promotion = JSON.parse(promoteString);
                    console.log("Promotion", promotion);
                    const promotionOperation = promotion.value.operation;

                    if (promotionOperation === "add") {
                    console.log("handling add promotion");
                    await _handleAddPromotion(
                        promotion,
                        accountId,
                        blockHeight,
                        blockTimestamp,
                        receiptId
                    );
                    return;
                    } else {
                    // if an operation is implemented, we can handle it here
                    console.log("Operation not implemented");
                    }
                }

                async function _handleAddPromotion(
                    promotion,
                    accountId,
                    blockHeight,
                    blockTimestamp,
                    receiptId
                ) {
                    // Add your code here
                    const postAuthor = promotion.value.post.path.split("/")[0];
                    const postBlockHeight = promotion.value.post.blockHeight;
                    const promotionType = promotion.value.type;

                    console.log("Post Author", postAuthor);
                    console.log("Post Block Height", postBlockHeight);
                    console.log("Promotion Type", promotionType);
                    try {
                    const posts = await context.db.Posts.select(
                        { account_id: postAuthor, block_height: postBlockHeight },
                        1
                    );

                    if (posts.length > 0) {
                        const post = posts[0];
                        let content = JSON.parse(post.content);

                        console.log("Post found in database", post);
                        console.log("Post content", content);

                        delete promotion["item"];

                        const promotionData = {
                        account_id: accountId,
                        receipt_id: receiptId,
                        block_height: blockHeight,
                        block_timestamp: blockTimestamp,
                        promotion_type: promotionType,
                        post_id: post.id,
                        };

                        // Call GraphQL mutation to insert a new promotion
                        await context.db.Promote.insert(promotionData);

                        console.log(`Promotion by ${accountId} has been added to the database`);
                    }
                    } catch (e) {
                    console.log("Error handling add promotion", JSON.stringify(e));
                    }
                }

                async function handleRepost(
                    accountId,
                    blockHeight,
                    blockTimestamp,
                    receiptId,
                    repostContent
                ) {
                    try {
                    console.log("Reposts are a WIP repostContent:", repostContent);

                    const content = JSON.parse(repostContent);

                    if (content[1]?.value?.type !== "repost") {
                        console.log("Skipping non-repost content", content);
                        return;
                    }

                    console.log("Reposts are a WIP content:", content);
                    const postAuthor = content[1].key.path.split("/")[0];
                    const postBlockHeight = content[1].key.blockHeight;

                    console.log("Reposts are a WIP postAuthor:", postAuthor);
                    console.log("Reposts are a WIP blockHeight:", postBlockHeight);

                    try {
                        const posts = await context.db.Posts.select(
                        { account_id: postAuthor, block_height: postBlockHeight },
                        1
                        );
                        console.log(`posts: ${JSON.stringify(posts)}`, posts);
                        if (posts.length == 0) {
                        return;
                        }

                        const post = posts[0];
                        const accountsReposted =
                        post.accounts_reposted.length === 0
                            ? post.accounts_reposted
                            : JSON.parse(post.accounts_reposted);
                        if (accountsReposted.indexOf(accountId) === -1) {
                        accountsReposted.push(accountId);
                        }

                        try {
                        const repostData = {
                            post_id: post.id,
                            account_id: accountId,
                            content: JSON.stringify(content),
                            block_height: blockHeight,
                            block_timestamp: blockTimestamp,
                            receipt_id: receiptId,
                        };
                        // Call GraphQL mutation to insert a new repost
                        await context.db.Reposts.insert(repostData);
                        console.log(`Repost by ${accountId} has been added to the database`);

                        // Call GraphQL mutation to update a post's reposted accounts list
                        await context.db.Posts.update(
                            { id: post.id },
                            { accounts_reposted: JSON.stringify(accountsReposted) }
                        );
                        console.log(`Repost by ${accountId} has been added to the database`);
                        } catch (e) {
                        console.log(
                            `Failed to store repost to the post ${postAuthor}/${postBlockHeight} by ${accountId} perhaps it has already been stored. Error ${e}`
                        );
                        }
                    } catch (e) {
                        console.log(
                        `Failed to store repost to the post ${postAuthor}/${postBlockHeight} as we don't have it stored in the first place. Error ${e}`
                        );
                    }
                    } catch (error) {
                    console.log("Failed to parse repost content. Skipping...", error);
                    }
                }

                // Add your code here
                const SOCIAL_DB = "social.near";

                let nearSocialPosts = [];
                try {
                    const actions = block.actions();
                    if (!actions) {
                    console.log("Block has no actions");
                    return;
                    }
                    const contractActions = actions.filter(
                    (action) => action.receiverId === SOCIAL_DB
                    );
                    if (!contractActions) {
                    console.log("Block has no actions");
                    return;
                    }
                    nearSocialPosts = contractActions.flatMap((action) =>
                    action.operations
                        .map((operation) => operation["FunctionCall"])
                        .filter((operation) => operation?.methodName === "set")
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
                            !functionCall.args.data ||
                            !Object.keys(functionCall.args.data) ||
                            !Object.keys(functionCall.args.data)[0]
                            ) {
                            console.log(
                                "Set operation did not have arg data in expected format"
                            );
                            return;
                            }
                            const accountId = Object.keys(functionCall.args.data)[0];
                            return (
                            Object.keys(functionCall.args.data[accountId]).includes("post") ||
                            Object.keys(functionCall.args.data[accountId]).includes("index")
                            );
                        } catch (e) {
                            console.log("Error parsing social args", functionCall);
                        }
                        })
                    );
                } catch (e) {
                    console.log("Error parsing social operations", block.actions());
                }

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
                            accountId,
                            blockHeight,
                            blockTimestamp,
                            postAction.receiptId,
                            postAction.args.data[accountId].post.main
                        );
                        } else if (
                        postAction.args.data[accountId].post &&
                        Object.keys(postAction.args.data[accountId].post).includes("comment")
                        ) {
                        // if creates a comment
                        await handleCommentCreation(
                            accountId,
                            blockHeight,
                            blockTimestamp,
                            postAction.receiptId,
                            postAction.args.data[accountId].post.comment
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
                            accountId,
                            blockHeight,
                            blockTimestamp,
                            postAction.receiptId,
                            postAction.args.data[accountId].index.like
                            );
                        }

                        if (
                            Object.keys(postAction.args.data[accountId].index).includes(
                            "promote"
                            )
                        ) {
                            console.log("handling promotion");
                            await handlePromotion(
                            accountId,
                            blockHeight,
                            blockTimestamp,
                            postAction.receiptId,
                            postAction.args.data[accountId].index.promote
                            );
                        }

                        // Probably repost action is happening
                        if (
                            Object.keys(postAction.args.data[accountId].index).includes(
                            "repost"
                            )
                        ) {
                            console.log("handling repost");
                            await handleRepost(
                            accountId,
                            blockHeight,
                            blockTimestamp,
                            postAction.receiptId,
                            postAction.args.data[accountId].index.repost
                            );
                        }
                        }
                    })
                    );
                }
                }`,
                "explanation": "This code creates a blockchain indexer using NEAR QueryAPI to handle, transform, and record data from relevant blockchain transactions. The main logic filters transaction data to process and save interactions involving the social.near account. The schema defines tables for posts, comments, and likes, ensuring efficient data querying. Helper functions decode base64 arguments, handle post and comment creation, and manage likes. The indexer also includes GraphQL queries for fetching data from the indexer's database, with an example NEAR component that demonstrates how to query and display post likes.
                To improve coding practices, we defined all helper functions at the beginning of the script before the main logic, and declared constants (SOCIAL_DB) inside the main function but outside the primary logic block for clarity. We also used a detailed and nested approach to parse and handle data, including filtering operations and handling specific cases as needed. Explicitly we handle handle different actions (posts, comments, likes, promotions, and reposts) with separate, well-defined functions and include detailed logging and error messages for various failure cases to aid in debugging and provide clearer information.
                We included helper functions for handling likes (_handlePostLike, _handlePostUnlike) and placed them before the main logic and checked to decode arguments in a detailed manner to ensure data is in the expected format before processing. For example, when handling post creation, first check if the post already exists in the database. If it does not, proceed to insert the post and log success; otherwise, log that the post already exists. Use this structured approach to create robust, maintainable, and clear code, ensuring all edge cases and potential errors are handled appropriately."
                """.replace('{','{{').replace('}','}}'),
            ),
            ( #few shot example with QueryAPI Indexer
                "human",
                """Here is the relevant context code:
                Postgresql schema: `CREATE TABLE indexers (
                    author_account_id TEXT NOT NULL,
                    indexer_name TEXT NOT NULL,
                    deployment_receipt_id TEXT NOT NULL,
                    deployment_timestamp TIMESTAMP NOT NULL,
                    deployment_block_height NUMERIC(20) NOT NULL,
                    deployment_start_from_block_height NUMERIC(20),
                    deployment_contract_filter TEXT,
                    last_change_receipt_id TEXT NOT NULL,
                    last_change_timestamp TIMESTAMP NOT NULL,
                    last_change_block_height NUMERIC(20) NOT NULL,
                    last_change_start_from_block_height NUMERIC(20),
                    last_change_contract_filter TEXT,
                    js_code TEXT NOT NULL,
                    sql_code TEXT NOT NULL,
                    is_removed BOOLEAN NOT NULL DEFAULT FALSE,
                    removed_timestamp TIMESTAMP,
                    removed_block_height NUMERIC(20),
                    removed_receipt_id TEXT,
                    PRIMARY KEY (author_account_id, indexer_name)
                );

                CREATE TABLE
                indexer_versions (
                    author_account_id TEXT NOT NULL,
                    indexer_name TEXT NOT NULL,
                    version_receipt_id TEXT NOT NULL,
                    version_timestamp TIMESTAMP NOT NULL,
                    version_block_height NUMERIC(20) NOT NULL,
                    version_start_from_block_height NUMERIC(20),
                    version_contract_filter TEXT,
                    js_code TEXT NOT NULL,
                    sql_code TEXT NOT NULL,
                    FOREIGN KEY (author_account_id, indexer_name) REFERENCES indexers (author_account_id, indexer_name),
                    PRIMARY KEY (
                    author_account_id,
                    indexer_name,
                    version_receipt_id
                    );`
                Javascript Function: `const queryApiContractTxs = block.functionCallsToReceiver('dev-queryapi.dataplatform.near')
                    .map((fxnCallView) => {
                        let decodedArgs;
                        try {
                        decodedArgs = fxnCallView.argsAsJSON();
                        } catch (error) {
                        decodedArgs = fxnCallView.args;
                        }
                        const functionName = decodedArgs.function_name;
                        const code = decodedArgs.code;
                        const schema = decodedArgs.schema;
                        const startFromBlockHeight = decodedArgs.start_block;
                        const contractFilter = decodedArgs.rule?.affected_account_id || '';
                        const accountId = fxnCallView.signerId;
                        const receiptId = fxnCallView.receiptId;

                        return {
                        accountId,
                        functionName,
                        receiptId,
                        code,
                        schema,
                        startFromBlockHeight,
                        contractFilter,
                        };
                    });

                    if (queryApiContractTxs.length > 0) {
                    console.log('Found QueryAPI Development Activity...');
                    const blockHeight = block.header().height;
                    const blockTimestamp = block.header().timestampNanosec;
                    await Promise.all(
                        queryApiContractTxs.map(
                        async ({
                            accountId,
                            functionName,
                            receiptId,
                            code,
                            schema,
                            startFromBlockHeight,
                            contractFilter,
                        }) => {
                            console.log(`Handling ${accountId}/${functionName} indexer...`);
                            try {
                            await handleIndexerEditTx(
                                accountId,
                                functionName,
                                receiptId,
                                code,
                                schema,
                                blockHeight,
                                blockTimestamp,
                                startFromBlockHeight,
                                contractFilter
                            );
                            } catch (err) {
                            console.log(`Error processing receipt at blockHeight: ${blockHeight}: ${err}`);
                            return err;
                            }
                        }
                        )
                    );
                }`,
                Entity Schema: `{\n  \"type\": \"array\",\n  \"items\": {\n    \"type\": \"object\",\n    \"properties\": {\n      \"receiverId\": {\n        \"type\": \"string\"\n      },\n      \"methodName\": {\n        \"type\": \"string\"\n      },\n      \"args\": {\n        \"type\": \"object\",\n        \"properties\": {\n          \"code\": {\n            \"type\": \"string\"\n          },\n          \"function_name\": {\n            \"type\": \"string\"\n          },\n          \"rule\": {\n            \"type\": \"object\",\n            \"properties\": {\n              \"affected_account_id\": {\n                \"type\": \"string\"\n              },\n              \"kind\": {\n                \"type\": \"string\"\n              },\n              \"status\": {\n                \"type\": \"string\"\n              }\n            },\n            \"required\": [\n              \"affected_account_id\",\n              \"kind\",\n              \"status\"\n            ]\n          },\n          \"schema\": {\n            \"type\": [\n              \"null\",\n              \"string\"\n            ]\n          },\n          \"start_block\": {\n            \"anyOf\": [\n              {\n                \"type\": \"string\"\n              },\n              {\n                \"type\": \"object\",\n                \"properties\": {\n                  \"HEIGHT\": {\n                    \"type\": \"integer\"\n                  }\n                },\n                \"required\": [\n                  \"HEIGHT\"\n                ]\n              }\n            ]\n          }\n        },\n        \"required\": [\n          \"function_name\"\n        ]\n      },\n      \"gas\": {\n        \"type\": \"integer\"\n      },\n      \"deposit\": {\n        \"type\": \"string\"\n      },\n      \"action\": {\n        \"type\": \"object\",\n        \"properties\": {\n          \"receiptId\": {\n            \"type\": \"string\"\n          },\n          \"receiptStatus\": {\n            \"type\": \"object\",\n            \"properties\": {\n              \"SuccessValue\": {\n                \"type\": \"string\"\n              },\n              \"Failure\": {\n                \"type\": \"object\",\n                \"properties\": {\n                  \"ActionError\": {\n                    \"type\": \"object\",\n                    \"properties\": {\n                      \"index\": {\n                        \"type\": \"integer\"\n                      },\n                      \"kind\": {\n                        \"type\": \"object\",\n                        \"properties\": {\n                          \"FunctionCallError\": {\n                            \"type\": \"object\",\n                            \"properties\": {\n                              \"ExecutionError\": {\n                                \"type\": \"string\"\n                              }\n                            },\n                            \"required\": [\n                              \"ExecutionError\"\n                            ]\n                          }\n                        },\n                        \"required\": [\n                          \"FunctionCallError\"\n                        ]\n                      }\n                    },\n                    \"required\": [\n                      \"index\",\n                      \"kind\"\n                    ]\n                  }\n                },\n                \"required\": [\n                  \"ActionError\"\n                ]\n              }\n            }\n          },\n          \"predecessorId\": {\n            \"type\": \"string\"\n          },\n          \"receiverId\": {\n            \"type\": \"string\"\n          },\n          \"signerId\": {\n            \"type\": \"string\"\n          },\n          \"signerPublicKey\": {\n            \"type\": \"string\"\n          },\n          \"operations\": {\n            \"type\": \"array\",\n            \"items\": {\n              \"type\": \"object\",\n              \"properties\": {\n                \"FunctionCall\": {\n                  \"type\": \"object\",\n                  \"properties\": {\n                    \"args\": {\n                      \"type\": \"string\"\n                    },\n                    \"deposit\": {\n                      \"type\": \"string\"\n                    },\n                    \"gas\": {\n                      \"type\": \"integer\"\n                    },\n                    \"methodName\": {\n                      \"type\": \"string\"\n                    }\n                  },\n                  \"required\": [\n                    \"args\",\n                    \"deposit\",\n                    \"gas\",\n                    \"methodName\"\n                  ]\n                }\n              },\n              \"required\": [\n                \"FunctionCall\"\n              ]\n            }\n          },\n          \"logs\": {\n            \"type\": \"array\",\n            \"items\": {\n              \"type\": \"string\"\n            }\n          }\n        },\n        \"required\": [\n          \"logs\",\n          \"operations\",\n          \"predecessorId\",\n          \"receiptId\",\n          \"receiptStatus\",\n          \"receiverId\",\n          \"signerId\",\n          \"signerPublicKey\"\n        ]\n      }\n    },\n    \"required\": [\n      \"action\",\n      \"args\",\n      \"deposit\",\n      \"gas\",\n      \"methodName\",\n      \"receiverId\"\n    ]\n  }\n}"
                """.replace('{','{{').replace('}','}}'),
            ),
            (
                "ai",
                """
                "data_upsertion_code":`import * as primitives from "@near-lake/primitives";
                async function getBlock(block: primitives.Block) {
                const QUERY_API_MAINNET = "dev-queryapi.dataplatform.near";

                function convertNanosecondsToTimestamp(nanosecondsStr) {
                    const nanoseconds = BigInt(nanosecondsStr);
                    const milliseconds = nanoseconds / 1000000n;
                    const date = new Date(Number(milliseconds));
                    return date;
                }

                // Handle "register_indexer_function" methods
                async function handleIndexerEditTx(
                    accountId,
                    functionName,
                    receiptId,
                    code,
                    schema,
                    blockHeight,
                    blockTimestamp,
                    startFromBlockHeight,
                    contractFilter
                ) {
                    const edit_indexer = {
                    author_account_id: accountId,
                    indexer_name: functionName,
                    deployment_receipt_id: receiptId,
                    deployment_timestamp: convertNanosecondsToTimestamp(blockTimestamp),
                    deployment_block_height: blockHeight,
                    deployment_start_from_block_height: startFromBlockHeight,
                    deployment_contract_filter: contractFilter,
                    last_change_receipt_id: receiptId,
                    last_change_timestamp: convertNanosecondsToTimestamp(blockTimestamp),
                    last_change_block_height: blockHeight,
                    last_change_start_from_block_height: startFromBlockHeight,
                    last_change_contract_filter: contractFilter,
                    is_removed: false,
                    removed_receipt_id: null,
                    removed_timestamp: null,
                    removed_block_height: null,
                    js_code: code,
                    sql_code: schema,
                    };

                    const edit_version = {
                    author_account_id: accountId,
                    indexer_name: functionName,
                    version_receipt_id: receiptId,
                    version_timestamp: convertNanosecondsToTimestamp(blockTimestamp),
                    version_block_height: blockHeight,
                    version_start_from_block_height: startFromBlockHeight,
                    version_contract_filter: contractFilter,
                    js_code: code,
                    sql_code: schema,
                    };

                    try {
                    const insertResult = await context.db.Indexers.upsert(
                        edit_indexer,
                        ["author_account_id", "indexer_name"],
                        [
                        "last_change_receipt_id",
                        "last_change_timestamp",
                        "last_change_block_height",
                        "last_change_start_from_block_height",
                        "last_change_contract_filter",
                        "js_code",
                        "sql_code",
                        "is_removed",
                        "removed_receipt_id",
                        "removed_timestamp",
                        "removed_block_height",
                        ]
                    );

                    const insertVersionResult = await context.db.IndexerVersions.upsert(
                        edit_version,
                        ["author_account_id", "indexer_name", "version_receipt_id"],
                        [
                        "version_timestamp",
                        "version_block_height",
                        "version_start_from_block_height",
                        "version_contract_filter",
                        "js_code",
                        "sql_code",
                        ]
                    );
                    } catch (err) {
                    console.log(
                        `Failed to add indexer edit to the db at blockHeight: ${blockHeight}, ${err}`
                    );
                    }
                }

                const queryApiContractTxs = block
                    .functionCalls(QUERY_API_MAINNET, "onlySuccessful")
                    .filter((functionCall) => functionCall.methodName.startsWith("register"))
                    .map((functionCall) => {
                    const argsAsJSON = functionCall.argsAsJSON();
                    const functionName = argsAsJSON.function_name;
                    const code = argsAsJSON.code;
                    const schema = argsAsJSON.schema;
                    const startFromBlockHeight = argsAsJSON.start_block_height;
                    const contractFilter = argsAsJSON.filter_json
                        ? JSON.parse(argsAsJSON.filter_json).matching_rule.affected_account_id
                        : "";
                    const accountId = functionCall.signerId;
                    const receiptId = functionCall.receiptId;
                    return {
                        accountId,
                        functionName,
                        receiptId,
                        code,
                        schema,
                        startFromBlockHeight,
                        contractFilter,
                    };
                    });

                if (queryApiContractTxs.length > 0) {
                    console.log("Found QueryAPI Development Activity...");
                    const blockHeight = block.header().height;
                    const blockTimestamp = block.header().timestampNanosec;
                    await Promise.all(
                    queryApiContractTxs.map(
                        async ({
                        accountId,
                        functionName,
                        receiptId,
                        code,
                        schema,
                        startFromBlockHeight,
                        contractFilter,
                        }) => {
                        console.log(`Handling ${accountId}/${functionName} indexer...`);
                        try {
                            await handleIndexerEditTx(
                            accountId,
                            functionName,
                            receiptId,
                            code,
                            schema,
                            blockHeight,
                            blockTimestamp,
                            startFromBlockHeight,
                            contractFilter
                            );
                        } catch (err) {
                            console.log(
                            `Error processing receipt at blockHeight: ${blockHeight}: ${err}`
                            );
                            return err;
                        }
                        }
                    )
                    );
                }

                // Handle "remove_indexer_function" methods
                async function handleIndexerRemoveTx(
                    accountId,
                    functionName,
                    receiptId,
                    blockHeight,
                    blockTimestamp
                ) {
                    try {
                    const removeResult = await context.db.Indexers.update(
                        { author_account_id: accountId, indexer_name: functionName },
                        {
                        removed_receipt_id: receiptId,
                        removed_timestamp: convertNanosecondsToTimestamp(blockTimestamp),
                        removed_block_height: blockHeight,
                        is_removed: true,
                        }
                    );
                    } catch (err) {
                    console.log(
                        `Failed to remove indexer to the db at blockHeight: ${blockHeight}, ${err}`
                    );
                    }
                }
                const queryApiRemoveContractTxs = block
                    .functionCalls(QUERY_API_MAINNET, "onlySuccessful")
                    .filter(
                    (functionCall) => functionCall.methodName === "remove_indexer_function"
                    )
                    .map((functionCall) => {
                    const argsAsJSON = functionCall.argsAsJSON();
                    const functionName = argsAsJSON.function_name;
                    const accountId = functionCall.action.signerId;
                    const receiptId = functionCall.action.receiptId;
                    return { accountId, functionName, receiptId };
                    });

                if (queryApiRemoveContractTxs.length > 0) {
                    const blockHeight = block.header().height;
                    const blockTimestamp = block.header().timestampNanosec;
                    await Promise.all(
                    queryApiRemoveContractTxs.map(
                        async ({ accountId, functionName, receiptId }) => {
                        console.log(`Removing ${accountId}/${functionName} indexer...`);
                        try {
                            await handleIndexerRemoveTx(
                            accountId,
                            functionName,
                            receiptId,
                            blockHeight,
                            blockTimestamp
                            );
                        } catch (err) {
                            console.log(
                            `Error processing receipt at blockHeight: ${blockHeight}: ${err}`
                            );
                            return err;
                        }
                        }
                    )
                    );
                }
                }`,
                "explanation": "This JavaScript code is designed to process NEAR blockchain blocks, focusing on transactions related to registering and removing indexer functions. Key improvements include null checks using optional chaining to handle potential null values, enhanced error handling within the handleIndexerDeployment function to log detailed error messages and return null on failure, ensuring the function returns the result of the upsert operation for better tracking of success or failure, and adding a check to skip further processing if deployment handling fails. The code also converts nanoseconds to JavaScript Date objects, processes transactions for registering or updating indexer functions by constructing and upserting objects into a database, filters transactions to find and process successful calls to "register_indexer_function" and "remove_indexer_function" methods, and updates the database to mark indexers as removed. This approach ensures robust handling of potential errors and null values, prevents database constraint violations, and improves the overall reliability and efficiency of processing blockchain data for indexer management."
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