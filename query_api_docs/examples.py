def hardcoded_block_extractor_js():
    return """
    function extractData(block) {
            const actions = block.actions();
            const receipts = block.receipts();
            const header = block.header();

            const successfulReceipts = receipts.filter(receipt => receipt.status.SuccessValue);
            const filteredActions = actions.filter(action => action.receiverId === 'app.nearcrowd.near' && action.operations.some(op => op.FunctionCall));

            const result = [];

            for (const action of filteredActions) {
            for (const operation of action.operations) {
                if (operation.FunctionCall) {
                const receipt = receipts.find(receipt => receipt.receiptId === action.receiptId);
                if (receipt) {
                    const args = JSON.parse(atob(operation.FunctionCall.args));
                    result.push({
                    signerId: action.signerId,
                    blockHeight: header.height,
                    receiptId: action.receiptId,
                    receipt: receipt,
                    blockDatetime: new Date(parseInt(header.timestampNanosec) / 1000000),
                    methodName: operation.FunctionCall.methodName,
                    ...args
                    });
                }
                }
            }
            }

            return result;
        }
        return extractData(block);
    """

def get_example_extract_block_code():
    return """
    const SOCIAL_DB = "social.near";

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
    """


def get_example_extract_block_code():
    return """
    const SOCIAL_DB = "social.near";

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
    """

def get_example_indexer_logic():
    return """
    // The following code is the target PostgreSQL table that data is inserted into
    // CREATE TABLE "posts" (
    //     "id" SERIAL NOT NULL,
    //     "account_id" VARCHAR NOT NULL,
    //     "block_height" DECIMAL(58, 0) NOT NULL,
    //     "receipt_id" VARCHAR NOT NULL,
    //     "content" TEXT NOT NULL,
    //     "block_timestamp" DECIMAL(20, 0) NOT NULL,
    //     CONSTRAINT "posts_pkey" PRIMARY KEY ("id")
    // );

    // The following code is the JavaScript code that moves data from the blockchain to the PostgreSQL table
    import { Block } from "@near-lake/primitives";

    async function getBlock(block: Block, context) {
    function base64decode(encodedValue) {
        let buff = Buffer.from(encodedValue, "base64");
        return JSON.parse(buff.toString("utf-8"));
    }

    const SOCIAL_DB = "social.near";

    const nearSocialPosts = block
        .actions()
        .filter((action) => action.receiverId === SOCIAL_DB)
        .flatMap((action) =>
        action.operations
            .map((operation) => operation["FunctionCall"])
            .filter((operation) => operation?.method_name === "set")
            .map((functionCallOperation) => ({
            ...functionCallOperation,
            args: base64decode(functionCallOperation.args),
            receiptId: action.receiptId,
            }))
            .filter((functionCall) => {
            const accountId = Object.keys(functionCall.args.data)[0];
            return (
                Object.keys(functionCall.args.data[accountId]).includes("post") ||
                Object.keys(functionCall.args.data[accountId]).includes("index")
            );
            })
        );
        if (nearSocialPosts.length > 0) {
        const blockHeight = block.blockHeight;
        const blockTimestamp = Number(block.header().timestampNanosec);
        await Promise.all(
        nearSocialPosts.map(async (postAction) => {
            const accountId = Object.keys(postAction.args.data)[0];
            console.log(`ACCOUNT_ID: ${accountId}`);

            // create a post if indeed a post
            if (
            postAction.args.data[accountId].post &&
            Object.keys(postAction.args.data[accountId].post).includes("main")
            ) {
            try {
                console.log("Creating a post...");
                const postData = {
                    account_id: accountId,
                    block_height: blockHeight,
                    block_timestamp: blockTimestamp,
                    receipt_id: postAction.receiptId,
                    content: postAction.args.data[accountId].post.main,
                };
                await context.db.Posts.insert(postData);
                console.log(`Post by ${accountId} has been added to the database`);
            } catch (e) {
                console.error(`Error creating a post by ${accountId}: ${e}`);
            }
            }
        })
        );
        }
    }
    """