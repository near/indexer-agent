import { StateChangeWithCauseView } from './core/types';
import { AccessKey } from './receipts';
/**
 * This structure is almost an identical copy of the `StateChangeWithCauseView` from [near-primitives](https://github.com/near/nearcore/tree/master/core/primitives) with a propagated additional field `affectedAccountId`.
 */
export declare class StateChange {
    /**
     * Returns the `cause` of the `StateChange`.
     */
    readonly cause: StateChangeCause;
    /**
     * Returns the `value` of the `StateChange`.
     */
    readonly value: StateChangeValue;
    constructor(
    /**
     * Returns the `cause` of the `StateChange`.
     */
    cause: StateChangeCause, 
    /**
     * Returns the `value` of the `StateChange`.
     */
    value: StateChangeValue);
    /**
     * Returns the account id of the `StateChange`.
     */
    get affectedAccountId(): string;
    /**
     * Returns the `StateChange` from the `StateChangeWithCauseView`. Created for backward compatibility.
     */
    static fromStateChangeView(stateChangeView: StateChangeWithCauseView): StateChange;
}
type TransactionProcessingCause = {
    txHash: string;
};
type ActionReceiptProcessingStartedCause = {
    receiptHash: string;
};
type ActionReceiptGasRewardCause = {
    receiptHash: string;
};
type ReceiptProcessingCause = {
    receiptHash: string;
};
type PostponedReceiptCause = {
    receiptHash: string;
};
type StateChangeCause = 'NotWritableToDisk' | 'InitialState' | TransactionProcessingCause | ActionReceiptProcessingStartedCause | ActionReceiptGasRewardCause | ReceiptProcessingCause | PostponedReceiptCause | 'UpdatedDelayedReceipts' | 'ValidatorAccountsUpdate' | 'Migration' | 'Resharding';
declare class AccountUpdateValue {
    readonly accountId: string;
    readonly account: Account;
    constructor(accountId: string, account: Account);
}
declare class AccountDeletionValue {
    readonly accountId: string;
    constructor(accountId: string);
}
declare class AccountKeyUpdateValue {
    readonly accountId: string;
    readonly publicKey: string;
    readonly accessKey: AccessKey;
    constructor(accountId: string, publicKey: string, accessKey: AccessKey);
}
declare class AccessKeyDeletionValue {
    readonly accountId: string;
    readonly publicKey: string;
    constructor(accountId: string, publicKey: string);
}
declare class DataUpdateValue {
    readonly accountId: string;
    readonly key: Uint8Array;
    readonly value: Uint8Array;
    constructor(accountId: string, key: Uint8Array, value: Uint8Array);
}
declare class DataDeletionValue {
    readonly accountId: string;
    readonly key: Uint8Array;
    constructor(accountId: string, key: Uint8Array);
}
declare class ContractCodeUpdateValue {
    readonly accountId: string;
    readonly code: Uint8Array;
    constructor(accountId: string, code: Uint8Array);
}
declare class ContractCodeDeletionValue {
    readonly accountId: string;
    constructor(accountId: string);
}
type StateChangeValue = AccountUpdateValue | AccountDeletionValue | AccountKeyUpdateValue | AccessKeyDeletionValue | DataUpdateValue | DataDeletionValue | ContractCodeUpdateValue | ContractCodeDeletionValue;
declare class Account {
    readonly amount: number;
    readonly locked: number;
    readonly codeHash: string;
    readonly storageUsage: number;
    readonly storagePaidAt: number;
    constructor(amount: number, locked: number, codeHash: string, storageUsage: number, storagePaidAt: number);
}
export {};
