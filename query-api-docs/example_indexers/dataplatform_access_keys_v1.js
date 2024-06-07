import * as primitives from "@near-lake/primitives";

async function getBlock(block: primitives.Block) {
  const startTime = Date.now();

  const blockDateTime = new Date(
    block.streamerMessage.block.header.timestamp / 1000000
  ).getTime();

  const actions = block.actions().filter((a) =>
    block
      .receipts()
      .find((r) => r.receiptId === a.receiptId)
      .status.hasOwnProperty("SuccessValue")
  );

  const addedKeys = actions.flatMap((a) => {
    return a.operations
      .filter((op) => op.AddKey)
      .flatMap((op) =>
        Object.keys(op).map((actionKind) => {
          return {
            public_key: op[actionKind].publicKey,
            permission_kind: op[actionKind].accessKey.permission.FunctionCall
              ? "FUNCTION_CALL"
              : "FULL_ACCESS",
            account_id: a.receiverId,
            created_by_receipt_id: a.receiptId,
            last_updated_block_height: block.blockHeight,
            block_timestamp_utc: new Date(blockDateTime).toISOString(),
            indexed_at_timestamp_utc: new Date(Date.now()).toISOString(),
            indexed_lag_in_seconds: (Date.now() - blockDateTime) / 1000,
          };
        })
      );
  });
  const deletedKeys = actions.flatMap((a) => {
    return a.operations
      .filter((op) => op.DeleteKey)
      .flatMap((op) =>
        Object.keys(op).map((actionKind) => {
          return {
            public_key: op[actionKind].publicKey,
            account_id: a.receiverId,
            deleted_by_receipt_id: a.receiptId,
            last_updated_block_height: block.blockHeight,
            block_timestamp_utc: new Date(blockDateTime).toISOString(),
            indexed_at_timestamp_utc: new Date(Date.now()).toISOString(),
            indexed_lag_in_seconds: (Date.now() - blockDateTime) / 1000,
          };
        })
      );
  });

  const deletedAccounts = actions.flatMap((a) => {
    return a.operations
      .filter((op) => op.DeleteAccount)
      .flatMap((op) =>
        Object.keys(op).map((actionKind) => {
          return {
            account_id: a.receiverId,
            deleted_by_receipt_id:
              actionKind === "DeleteAccount" ? a.receiptId : null,
            last_updated_block_height: block.blockHeight,
            block_timestamp_utc: new Date(blockDateTime).toISOString(),
            indexed_at_timestamp_utc: new Date(Date.now()).toISOString(),
            indexed_lag_in_seconds: (Date.now() - blockDateTime) / 1000,
          };
        })
      );
  });

  await Promise.all([
    context.db.AccessKeysV1.upsert(
      addedKeys,
      ["public_key", "account_id"],
      [
        "deleted_by_receipt_id",
        "last_updated_block_height",
        "block_timestamp_utc",
        "indexed_at_timestamp_utc",
        "indexed_lag_in_seconds",
      ]
    ),
    ...deletedAccounts.map((da) =>
      context.db.AccessKeysV1.update(
        { account_id: da.account_id },
        {
          account_deleted_by_receipt_id: da.deleted_by_receipt_id,
          last_updated_block_height: da.last_updated_block_height,
          block_timestamp_utc: da.block_timestamp_utc,
          indexed_at_timestamp_utc: da.indexed_at_timestamp_utc,
          indexed_lag_in_seconds: da.indexed_lag_in_seconds,
        }
      )
    ),
    ...deletedKeys.map((da) =>
      context.db.AccessKeysV1.update(
        { account_id: da.account_id, public_key: da.public_key },
        {
          deleted_by_receipt_id: da.deleted_by_receipt_id,
          last_updated_block_height: da.last_updated_block_height,
          block_timestamp_utc: da.block_timestamp_utc,
          indexed_at_timestamp_utc: da.indexed_at_timestamp_utc,
          indexed_lag_in_seconds: da.indexed_lag_in_seconds,
        }
      )
    ),
  ]);
  const endTime = Date.now();
  console.log(startTime, " to ", endTime, "lag", (endTime - startTime) / 1000);
}
