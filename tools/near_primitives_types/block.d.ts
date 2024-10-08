import { Action, Receipt } from './receipts';
import { StreamerMessage, ValidatorStakeView } from './core/types';
import { Transaction } from './transactions';
import { Event, Log } from './events';
import { StateChange } from './stateChanges';
/**
 * The `Block` type is used to represent a block in the NEAR Lake Framework.
 *
 * **Important Notes on `Block`:**
 * - All the entities located on different shards were merged into one single list without differentiation.
 * - `Block` is not the fairest name for this structure either. NEAR Protocol is a sharded blockchain, so its block is actually an ephemeral structure that represents a collection of real blocks called chunks in NEAR Protocol.
 */
export declare class Block {
    /**
     * Low-level structure for backward compatibility.
     * As implemented in previous versions of [`near-lake-framework`](https://www.npmjs.com/package/near-lake-framework).
     */
    readonly streamerMessage: StreamerMessage;
    private executedReceipts;
    /**
     * Receipts included on the chain but not executed yet marked as “postponed”: they are represented by the same structure `Receipt` (see the corresponding section in this doc for more details).
     */
    readonly postponedReceipts: Receipt[];
    /**
     * List of included `Transactions`, converted into `Receipts`.
     *
     * **_NOTE_:** Heads up! You might want to know about `Transactions` to know where the action chain has begun. Unlike Ethereum, where a Transaction contains everything you may want to know about a particular interaction on  the Ethereum blockchain, Near Protocol because of its asynchronous nature converts a `Transaction` into a `Receipt` before executing it. Thus, On NEAR, `Receipts` are more important for figuring out what happened on-chain as a result of a Transaction signed by a user. Read more about [Transactions on Near](https://nomicon.io/RuntimeSpec/Transactions) here.
     *
     */
    readonly transactions: Transaction[];
    private _actions;
    private _events;
    private _stateChanges;
    constructor(
    /**
     * Low-level structure for backward compatibility.
     * As implemented in previous versions of [`near-lake-framework`](https://www.npmjs.com/package/near-lake-framework).
     */
    streamerMessage: StreamerMessage, executedReceipts: Receipt[], 
    /**
     * Receipts included on the chain but not executed yet marked as “postponed”: they are represented by the same structure `Receipt` (see the corresponding section in this doc for more details).
     */
    postponedReceipts: Receipt[], 
    /**
     * List of included `Transactions`, converted into `Receipts`.
     *
     * **_NOTE_:** Heads up! You might want to know about `Transactions` to know where the action chain has begun. Unlike Ethereum, where a Transaction contains everything you may want to know about a particular interaction on  the Ethereum blockchain, Near Protocol because of its asynchronous nature converts a `Transaction` into a `Receipt` before executing it. Thus, On NEAR, `Receipts` are more important for figuring out what happened on-chain as a result of a Transaction signed by a user. Read more about [Transactions on Near](https://nomicon.io/RuntimeSpec/Transactions) here.
     *
     */
    transactions: Transaction[], _actions: Map<string, Action>, _events: Map<string, Event[]>, _stateChanges: StateChange[]);
    /**
     * Returns the block hash. A shortcut to get the data from the block header.
     */
    get blockHash(): string;
    /**
     * Returns the previous block hash. A shortcut to get the data from the block header.
     */
    get prevBlockHash(): string;
    /**
     * Returns the block height. A shortcut to get the data from the block header.
     */
    get blockHeight(): number;
    /**
     * Returns a `BlockHeader` structure of the block
     * See `BlockHeader` structure sections for details.
     */
    header(): BlockHeader;
    /**
     * Returns a slice of `Receipts` executed in the block.
     * Basically is a getter for the `executedReceipts` field.
     */
    receipts(): Receipt[];
    /**
     * Returns an Array of `Actions` executed in the block.
     */
    actions(): Action[];
    /**
     * Returns `Events` emitted in the block.
     */
    events(): Event[];
    /**
     * Returns raw logs regardless of the fact that they are standard events or not.
     */
    logs(): Log[];
    /**
     * Returns an Array of `StateChange` occurred in the block.
     */
    stateChanges(): StateChange[];
    /**
     * Returns `Action` of the provided `receipt_id` from the block if any. Returns `undefined` if there is no corresponding `Action`.
     *
     * This method uses the internal `Block` `action` field which is empty by default and will be filled with the block’s actions on the first call to optimize memory usage.
     *
     * The result is either `Action | undefined` since there might be a request for an `Action` by `receipt_id` from another block, in which case this method will be unable to find the `Action` in the current block. In the other case, the request might be for an `Action` for a `receipt_id` that belongs to a `DataReceipt` where an action does not exist.
     */
    actionByReceiptId(receipt_id: string): Action | undefined;
    /**
     * Returns an Array of Events emitted by `ExecutionOutcome` for the given `receipt_id`. There might be more than one `Event` for the `Receipt` or there might be none of them. In the latter case, this method returns an empty Array.
     */
    eventsByReceiptId(receipt_id: string): Event[];
    /**
     * Returns an Array of Events emitted by `ExecutionOutcome` for the given `account_id`. There might be more than one `Event` for the `Receipt` or there might be none of them. In the latter case, this method returns an empty Array.
     */
    eventsByAccountId(account_id: string): Event[];
    private buildActionsHashmap;
    private buildEventsHashmap;
    static fromStreamerMessage(streamerMessage: StreamerMessage): Block;
}
/**
 * Replacement for `BlockHeaderView` from [near-primitives](https://github.com/near/nearcore/tree/master/core/primitives). Shrunken and simplified.
 *
 * **Note:** the original `BlockHeaderView` is still accessible via the `.streamerMessage` attribute.
 */
export declare class BlockHeader {
    readonly height: number;
    readonly hash: string;
    readonly prevHash: string;
    readonly author: string;
    readonly timestampNanosec: string;
    readonly epochId: string;
    readonly nextEpochId: string;
    readonly gasPrice: string;
    readonly totalSupply: string;
    readonly latestProtocolVersion: number;
    readonly randomValue: string;
    readonly chunksIncluded: number;
    readonly validatorProposals: ValidatorStakeView[];
    constructor(height: number, hash: string, prevHash: string, author: string, timestampNanosec: string, epochId: string, nextEpochId: string, gasPrice: string, totalSupply: string, latestProtocolVersion: number, randomValue: string, chunksIncluded: number, validatorProposals: ValidatorStakeView[]);
    static fromStreamerMessage(streamerMessage: StreamerMessage): BlockHeader;
}
