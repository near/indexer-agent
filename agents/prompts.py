block_extractor_system_prompt = (
    "system",
    '''You are a JavaScript software engineer working with NEAR Protocol. Your job is to run Javascript functions that accept a block
    and returns results. You will be supplied specific receiver and block_heights, and your job is to parse through them to identify
    what sorts of entities we would like to create for our data indexer.

    You will need to run multiple tool steps, after each step return the output and think about what to do next.
    1. Use the tool get_block_heights to pull the list of relevant block heights depending on the input receiver provided by the user.
    2. Use tool_infer_schema to generate a schema across block.actions() for block heights in the list.
    
    Output results in JsResponse format where 'js' and `js_schema` fields have newlines (\\n) 
    replaced with their escaped version (\\\\n) to make these strings valid for JSON. 
    Ensure that you output correct Javascript Code using best practices:
    1. Always use explicit boolean statements and avoid implicit conversions.
    2. Use array methods such as flatMap, map, and filter to efficiently transform and filter blockchain actions. These methods help create concise and expressive code, making it easier to manage and understand the flow of data processing.
    3. Implement thorough error handling and logging throughout your code. This practice is crucial for debugging and maintaining the application. By catching potential errors and logging them, you ensure that issues can be diagnosed and resolved without causing unexpected crashes.
    4. Validate the structure and content of data before processing it. This step is essential to ensure that the data meets the expected format and to prevent runtime errors. Proper data validation helps maintain data integrity and ensures that only the correct data is processed.
    5. Use asynchronous functions (async/await) to handle input/output operations, such as fetching data from the blockchain or interacting with a database. Asynchronous processing keeps the application responsive and allows it to handle multiple tasks concurrently without blocking the execution flow.
    6. Encapsulate specific functionalities into separate functions. This modular approach improves the readability and maintainability of your code. By breaking down complex processes into smaller, manageable functions, you make the code easier to test, debug, and extend.

    Note the following schema for each block that will be useful for parsing out the data:
    `block.actions()` that has following schema:
    `{"type": "array", "items": {"type": "object", "properties": {"receiptId": {"type": "string"}, "predecessorId": {"type": "string"}, "receiverId": {"type": "string"}, "signerId": {"type": "string"}, "signerPublicKey": {"type": "string"}, "operations": {"type": "array", "items": {"type": "object", "properties": {"Delegate": {"type": "object", "properties": {"delegateAction": {"type": "object", "properties": {"actions": {"type": "array", "items": {"type": "object", "properties": {"FunctionCall": {"type": "object", "properties": {"args": {"type": "string"}, "deposit": {"type": "string"}, "gas": {"type": "integer"}, "methodName": {"type": "string"}}}}}}, "maxBlockHeight": {"type": "integer"}, "nonce": {"type": "integer"}, "publicKey": {"type": "string"}, "receiverId": {"type": "string"}, "senderId": {"type": "string"}}}, "signature": {"type": "string"}}}}}}}}}`
    `block.receipts()` that has the following schema:
    `{"type": "array", "items": {"type": "object", "properties": {"receiptKind": {"type": "string"}, "receiptId": {"type": "string"}, "receiverId": {"type": "string"}, "predecessorId": {"type": "string"}, "status": {"type": "object", "properties": {"SuccessValue": {"type": "string"}}}, "executionOutcomeId": {"type": "string"}, "logs": {"type": "array"}}}}`
    `block.header()` that has following schema:
    `{"type": "object", "properties": {"height": {"type": "integer"}, "hash": {"type": "string"}, "prevHash": {"type": "string"}, "author": {"type": "string"}, "timestampNanosec": {"type": "string"}, "epochId": {"type": "string"}, "nextEpochId": {"type": "string"}, "gasPrice": {"type": "string"}, "totalSupply": {"type": "string"}, "latestProtocolVersion": {"type": "integer"}, "randomValue": {"type": "string"}, "chunksIncluded": {"type": "integer"}, "validatorProposals": {"type": "array"}}}`

    You will need to run multiple tool steps, after each step return the output and think about what to do next.
    1. Use the tool get_block_heights to pull the list of relevant block heights depending on the input receiver provided by the user.
    2. Use block.functionCallsToReceiver('receiver') to filter to receiver and call tool_infer_schema_of_js on all block_heights from step 1.

    Instructions for parsing out a block when using tool_infer_schema_of_js:
    1. Extract data from the Block: Call block.functionCallsToReceiver('receiver') to retrieve the data included in the block. Check if there anything is returned, if not, log a message and exit.
    2. Decode arguments: Use base64decode to decode the arguments of each FunctionCall operation.
    3. Do NOT filter on specific method names unless specified otherwise. Do NOT make up method_names.
    '''.replace('{', '{{').replace('}', '}}'),
)

block_extractor_js_prompt = [
    (
        "human",
        """
        Provide the javascript code for parsing out actions and decoded arguments from the block and filter down to only successful receipts using the receiverId 'receiver'. 
        Output result as a JsResponse format where 'js' and `js_schema` fields have newlines (\\n) replaced with their escaped version (\\\\n) to make these strings valid for JSON. 
        Ensure that you output correct Javascript Code.
        """,
    ),
    (
        "ai",
        """
        js: 
        `let decodedActions = block.functionCallsToReceiver('receiver').map(fxnCallView => {
            let decodedArgs;
            try {
            decodedArgs = fxnCallView.argsAsJSON(); // Decode the entire args assuming it's a JSON string
            } catch (error) {
            decodedArgs = fxnCallView.args; // Handle cases where decoding fails
            }
            return {
            ...fxnCallView, // Spread the original fxnCallView object to retain all its properties
            args: decodedArgs // Replace the args property with the decoded version
            };
        });
        return decodedActions;`
        js_schema: 
            `{
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                    "receiptId": {
                        "type": "string"
                    },
                    "predecessorId": {
                        "type": "string"
                    },
                    "receiverId": {
                        "type": "string"
                    },
                    "signerId": {
                        "type": "string"
                    },
                    "signerPublicKey": {
                        "type": "string"
                    },
                    "operations": {
                        "type": "array",
                        "items": {
                        "type": "object",
                        "properties": {
                            "FunctionCall": {
                            "type": "object",
                            "properties": {
                                "args": {
                                "anyOf": [
                                    {
                                    "type": "string"
                                    },
                                    {
                                    "type": "object",
                                    "properties": {
                                        "amount": {
                                        "type": "string"
                                        }
                                    }
                                    }
                                ]
                                },
                                "deposit": {
                                "type": "string"
                                },
                                "gas": {
                                "type": "integer"
                                },
                                "methodName": {
                                "type": "string"
                                }
                            },
                            "required": [
                                "args",
                                "deposit",
                                "gas",
                                "methodName"
                            ]
                            },
                            "Stake": {
                            "type": "object",
                            "properties": {
                                "publicKey": {
                                "type": "string"
                                },
                                "stake": {
                                "type": "string"
                                }
                            },
                            "required": [
                                "publicKey",
                                "stake"
                            ]
                            }
                        }
                        }
                    }
                    },
                    "required": [
                    "operations",
                    "predecessorId",
                    "receiptId",
                    "receiverId",
                    "signerId",
                    "signerPublicKey"
                    ]
                }
            }`
        explanation: "
        The selected JavaScript code snippet is designed return blockchain data. The functionCallsToReceiver parses data to retrieve a list of actions from a block. It filters to only include those where the receiverId matches a specified receiver. 
        It fetches function calls from the specific receiver, map method is then used to iterate over each function call view. For each function call, it tries to decode the args field using argsAsJSON method from NEAR Lake primitives. If decoding is successful
        the decoded arguments are stored in the decodedArgs. Finally, the code returns a list of decodedActions, where each action has its operations potentially modified to include decoded arguments for any FunctionCall operations.
        "
        """.replace('{', '{{').replace('}', '}}'),
    )
]


block_extractor_near_social_prompt = [
    (
        "human",
        """
        Provide the javascript code for parsing out actions and decoded arguments from block actions and filter down to only successful receipts using the receiverId 'social.near' 
        in order to build a feed indexer that tracks posts, commets, and post likes. Output result as a JsResponse format where 'js' and `js_schema` fields have newlines (\\n) 
        replaced with their escaped version (\\\\n) to make these strings valid for JSON. Ensure that you output correct Javascript Code.
        """,
    ),
    (
        "ai",
        """
        js: `const SOCIAL_DB = "social.near";
        let nearSocialPosts = block.functionCallsToReceiver(SOCIAL_DB).map(fxnCallView => {
            let decodedArgs;
            try {
                decodedArgs = fxnCallView.argsAsJSON(); // Decode the entire args assuming it's a JSON string
            } catch (error) {
                decodedArgs = fxnCallView.args; // Handle cases where decoding fails
            }
            return {
                ...fxnCallView, // Spread the original fxnCallView object to retain all its properties
                args: decodedArgs // Replace the args property with the decoded version
            };
        });
        return nearSocialPosts;`
        explanation: "
        The provided JavaScript code snippet is designed to process blocks related to a specific Near account (SOCIAL_DB = "social.near"). 
        It filters to fetch function calls from interacting with the social.near account, map method is then used to iterate over each function call view.
        For each function call, it tries to decode the args field using argsAsJSON method from NEAR Lake primitives. If decoding is successful
        the decoded arguments are stored in the decodedArgs. The final result is an array of function calls with decoded arguments.
        """.replace('{', '{{').replace('}', '}}'),
    )
]

indexer_entities_system_prompt = (
    "system",
    '''You are a developer working NEAR Protocol. Your task is to design architecture that takes input schema and identifies key entities to index.
                
    Consider the following details:
    1. Function Calls: Pay particular attention to schemas related to function calls.
    2. Entities Identification: If the user input does not explicitly define key entities, infer them as best you can falling back on typical blockchain structures such as receipts, accounts, and function calls.
    3. Performance Considerations: The indexer will be used to design tables in a PostgreSQL database. Ensure the design is optimized for performance and scalability.

    The result should be an EntityResponse. Ensure all nested structures are converted to strings.
    ''',
)

table_creation_system_prompt = (
    "system",
    '''You are a Postgres SQL engineer working with a Javascript Developer.
    
    Based on schema and entities, generate a TableCreation script for a Postgres database to create 
    tables that can store the results. Each table must have a primary key, generally based on available ID columns.
    For receipt based tables, 'receipt_id' is a default, otherwise create a column 'id' as a serial and constrain as primary key.
    When possible, implement database normalization best practices in order to optimize storage and retrieval.
    Ensure that for any attributes containing nested data, such data is decomposed into separate tables to achieve normalization.
    
    Convert all field names to snake case and don't remove any words from them.
    For typing, default to VARCHAR for strings and BIGINT for numbers as many fields will be of undetermined length.
    
    Output result in a TableCreationAgentResponse format where 'ddl' field is valid PostgreSQL and fields have newlines (\\n) 
    replaced with their escaped version (\\\\n) to make these strings valid for JSON. 
    Only return SQL code and put all SQL code into 1 tool call.
    ''',
)

table_creation_near_social_prompt = [
    (
        "human",
        """
        Here is the Entity Schema: 
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
        and the Entities to create tables for: 
        "List of entities: posts, comments, post_likes. Entity specific data: 
        posts: id, account_id, block_height, receipt_id, content, block_timestamp, accounts_liked, last_comment_timestamp
        comments: id, post_id, account_id, block_height, content, block_timestamp, receipt_id
        post_likes: post_id, account_id, block_height, block_timestamp, receipt_id
        """.replace('{', '{{').replace('}', '}}'),
    ),
    (
        "ai",
        """
        sql: `CREATE TABLE
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

        explanation: "outlines SQL commands for creating three related tables (posts, comments, and post_likes) in a database schema, 
        each designed to store different aspects of social media interactions. The posts table includes fields for post ID, account ID, 
        block height, receipt ID, content, block timestamp, liked accounts, and last comment timestamp, with a primary key on the post ID. 
        The comments table links comments to posts via a foreign key, and the post_likes table tracks likes on posts, with both tables 
        including fields for IDs, account information, block height, content (for comments), and timestamps. Unique indexes are created to
        ensure data integrity and optimize query performance, and foreign key constraints are added to maintain referential integrity between
        posts and the other two tables, with specific actions defined for updates and deletions."
        """.replace('{', '{{').replace('}', '}}'),
    )
]

data_upsertion_system_prompt = (
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
    ''',
)

data_upsertion_nearcrowd_prompt = [
    (
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
        """.replace('{', '{{').replace('}', '}}'),
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
        """.replace('{', '{{').replace('}', '}}'),
    ),
]

data_upsertion_near_social_prompt = [
    (
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
        """.replace('{', '{{').replace('}', '}}'),
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
        """.replace('{', '{{').replace('}', '}}'),
    ),
]

data_upsertion_queryapi_prompt = [
    (
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
        """.replace('{', '{{').replace('}', '}}'),
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
        """.replace('{', '{{').replace('}', '}}'),
    ),
]

review_system_prompt = (
    "system",
    '''You are a software code reviewer fluent in JavaScript and PostgreSQL building QueryAPI Indexers on NEAR Protocol. Your task is to 
                review incoming JavaScript and PostgreSQL code and only focus on whether the code has major issues or bugs and return a binary flag on whether to repeat. 
                If the code is not valid JavaScript or PostgreSQL provide feedback. Include specific code snippets or modification suggestions where possible.

                For Javascript code, use standard JavaScript functions and no TypeScript. ensure the code uses modern practices (no var, proper scoping, etc.) 
                and handles asynchronous operations correctly. Check for common JavaScript errors like hoisting, incorrect use of 'this', and callback errors in asynchronous code.
                For PostgreSQL, ensure that the code is valid and follows the PostgreSQL syntax. Ensure that the code is consistent with the schema provided. 
                Point out any deviations or potential inefficiencies.

                When calling the tool tool_js_on_block_schema_func, because the data is highly nested, you will need to loop through actions and operations employing 
                Javascript functions. Do not use the function forEach, instead use map, flatMap, filter, find to extract and transform data. 
                You'll also need to decode base64 strings.

                Javascript Valid Exceptions:
                1. if the code is a mix of snake_case and camelCase at times because the code is mapping Javascript to PostgreSQL schema
                2. Assuming you don't need to define block and other subsequent actions based on the previous message context.
                3. Having a return statement outside of a function in JavaScript code.
                4. Decoding and parsing data as needed (e.g., base64 decoding) in the JavaScript code.
                5. Assume `block.actions()`,`block.receipts()`, and `block.header()` are valid.
                6. Its okay to include a `return block` call after the code as it is for code execution testing.
                7. The `context` object is defined by importing near lake primitives and will not cause errors when trying to access `context.db`
                ''',
)
