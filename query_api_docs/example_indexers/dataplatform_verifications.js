import * as primitives from "@near-lake/primitives";

async function getBlock(block: primitives.Block) {
  function base64decode(encodedValue) {
    let buff = Buffer.from(encodedValue, "base64");
    return JSON.parse(buff.toString("utf-8"));
  }
  const calls = block.actions().flatMap((action) =>
    action.operations
      .map((operation) => operation["FunctionCall"])
      .filter((operation) => operation?.methodName === "sbt_mint")
      .map((functionCallOperation) => ({
        ...functionCallOperation,
        args: base64decode(functionCallOperation.args),
      }))
  );

  for (let index in calls) {
    let call = calls[index];
    console.log("call", call);
    try {
      if (call.args.token_spec) {
        const accountId = call.args.token_spec[0][0];
        const issuance = call.args.token_spec[0][1][0];
        if (accountId && issuance) {
          const level = issuance.class ? issuance.class.toString() : "";
          const expires = new Date(issuance.expires_at).toISOString();
          const provider = "i-am-human.app";
          console.log(
            "found verification:",
            accountId,
            level,
            expires,
            provider
          );

          const mutationData = {
            account: {
              account_id: accountId,
              human_valid_until: expires,
              human_verification_level: level,
              human_provider: provider,
            },
          };

          await context.graphql(
            `mutation createAccount($account: dataplatform_near_verifications_account_insert_input!){
              insert_dataplatform_near_verifications_account_one(
                object: $account
                    on_conflict: {constraint: account_pkey, update_columns: [human_valid_until,human_verification_level, human_provider]}
              ) { account_id}
            }`,
            mutationData
          );
        } else {
          console.log("No account_id or issuance in this token spec");
        }
      } else {
        console.log("No token spec in this mint operation");
      }
    } catch (error) {
      console.log("Caught error", error);
    }
  }
}
