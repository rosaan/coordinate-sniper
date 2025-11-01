import { query, mutation } from "./_generated/server";
import { ConvexError, v } from "convex/values";
import { internal } from "./_generated/api";

/**
 * Generate a random 5-character alphanumeric code.
 */
function generateRandomCode(): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  let code = "";
  for (let i = 0; i < 5; i++) {
    code += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return code;
}

/**
 * Create a new user. Only firstName is required. clientCode is auto-generated as unique 5-character code.
 * Automatically queues a create_user operation for processing by the sync engine.
 */
export const createUser = mutation({
  args: {
    firstName: v.string(),
    lastName: v.optional(v.string()),
    telephone: v.optional(v.string()),
    email: v.optional(v.string()),
    recordingInstruction: v.optional(v.array(v.string())),
  },
  returns: v.object({
    userId: v.id("users"),
    operationId: v.id("operations"),
    message: v.string(),
  }),
  handler: async (ctx, args) => {
    // Generate unique 5-character clientCode
    let clientCode: string;
    let isUnique = false;
    let attempts = 0;
    const maxAttempts = 100; // Prevent infinite loop

    while (!isUnique && attempts < maxAttempts) {
      clientCode = generateRandomCode();

      // Check if code already exists
      const existing = await ctx.db
        .query("users")
        .withIndex("by_clientCode", (q) => q.eq("clientCode", clientCode))
        .first();

      if (!existing) {
        isUnique = true;
      } else {
        attempts++;
      }
    }

    if (!isUnique) {
      throw new Error(
        "Failed to generate unique client code after multiple attempts"
      );
    }

    // Create user
    const userId = await ctx.db.insert("users", {
      firstName: args.firstName,
      clientCode: clientCode!,
      lastName: args.lastName,
      telephone: args.telephone,
      email: args.email,
      recordingInstruction: args.recordingInstruction,
    });

    // Queue create_user operation using internal mutation
    const operationId = await ctx.runMutation(
      internal.operations.queueOperation,
      {
        operationType: "create_user",
        userId: userId,
        priority: 0, // Normal priority
      }
    );

    return {
      userId: userId,
      operationId: operationId,
      message: `User created and queued for processing: ${args.firstName} (${clientCode!})`,
    };
  },
});

/**
 * List all users that need processing (users not yet created locally).
 */
export const listPendingUsers = query({
  args: {},
  returns: v.array(
    v.object({
      _id: v.id("users"),
      _creationTime: v.number(),
      clientCode: v.string(),
      firstName: v.string(),
      lastName: v.optional(v.string()),
      telephone: v.optional(v.string()),
      email: v.optional(v.string()),
      recordingInstruction: v.optional(v.array(v.string())),
      isCreatedLocally: v.optional(v.boolean()),
      syncStatus: v.optional(v.string()),
      errorReason: v.optional(v.array(v.string())), // Array of error messages (stacks errors)
    })
  ),
  handler: async (ctx) => {
    const allUsers = await ctx.db.query("users").collect();
    // Filter users that haven't been created locally yet
    // Also exclude users with critical errors that need manual intervention
    // UNLESS they've been explicitly reset for retry (syncStatus === "pending")
    return allUsers.filter((user) => {
      // Include users explicitly marked as pending (including retries)
      if (user.syncStatus === "pending" || !user.syncStatus) {
        return true;
      }
      // Skip completed users
      if (user.isCreatedLocally === true) {
        return false;
      }
      // Skip users with critical errors (client_id_mismatch, delete_failed, mysql_error_deleted, clipboard_copy_failed)
      // These need manual intervention and shouldn't be retried automatically
      // UNLESS they've been reset via retryUser mutation
      if (
        user.syncStatus === "client_id_mismatch" ||
        user.syncStatus === "delete_failed" ||
        user.syncStatus === "mysql_error_deleted" ||
        user.syncStatus === "clipboard_copy_failed"
      ) {
        return false;
      }
      return true;
    });
  },
});

/**
 * Update a user with the recording link and mark as created locally.
 * Appends to recordingInstruction array instead of replacing (stacks data).
 */
export const updateRecordingLink = mutation({
  args: {
    userId: v.id("users"),
    recordingLink: v.string(),
  },
  returns: v.null(),
  handler: async (ctx, args) => {
    const user = await ctx.db.get(args.userId);
    if (!user) {
      throw new Error("User not found");
    }

    // Get existing recordingInstruction array or initialize empty array
    const existingInstructions = user.recordingInstruction || [];

    // Append new recording link (don't overwrite, stack the data)
    const updatedInstructions = [...existingInstructions, args.recordingLink];

    await ctx.db.patch(args.userId, {
      recordingInstruction: updatedInstructions,
      isCreatedLocally: true,
      syncStatus: "completed",
      errorReason: undefined,
    });
    return null;
  },
});

/**
 * Update user sync status and error reason.
 * Appends to errorReason array instead of replacing (stacks errors for history).
 */
export const updateSyncStatus = mutation({
  args: {
    userId: v.id("users"),
    syncStatus: v.string(),
    errorReason: v.optional(v.string()), // Single error message to append
  },
  returns: v.null(),
  handler: async (ctx, args) => {
    const user = await ctx.db.get(args.userId);
    if (!user) {
      throw new Error("User not found");
    }

    // Handle errorReason - stack errors in array
    let updatedErrorReasons: string[] | undefined = undefined;
    if (args.errorReason) {
      // Get existing errorReason array or convert string to array, or initialize empty array
      const existingErrors = user.errorReason;
      if (Array.isArray(existingErrors)) {
        // Append to existing array
        updatedErrorReasons = [...existingErrors, args.errorReason];
      } else if (typeof existingErrors === "string" && existingErrors) {
        // Convert existing string to array and append
        updatedErrorReasons = [existingErrors, args.errorReason];
      } else {
        // Initialize new array
        updatedErrorReasons = [args.errorReason];
      }
    } else {
      // If no new error provided, preserve existing (could be array or string)
      if (Array.isArray(user.errorReason)) {
        updatedErrorReasons = user.errorReason;
      } else if (typeof user.errorReason === "string" && user.errorReason) {
        updatedErrorReasons = [user.errorReason];
      }
      // else undefined, which means no errors
    }

    await ctx.db.patch(args.userId, {
      syncStatus: args.syncStatus,
      errorReason: updatedErrorReasons,
    });
    return null;
  },
});

/**
 * Reset a user for retry - clears sync status and marks as pending.
 * Preserves both recordingInstruction and errorReason arrays (doesn't clear them - data is stacked for history).
 * This allows users that failed or were skipped to be retried while keeping error history.
 */
export const retryUser = mutation({
  args: {
    userId: v.id("users"),
  },
  returns: v.null(),
  handler: async (ctx, args) => {
    const user = await ctx.db.get(args.userId);
    if (!user) {
      throw new ConvexError("User not found");
    }

    console.log("user", user);

    if (user.syncStatus === "processing" || user.syncStatus === "completed") {
      throw new ConvexError(
        "Cannot retry while user is being processed or completed"
      );
    }

    await ctx.db.patch(args.userId, {
      syncStatus: "pending",
      // Do NOT clear errorReason - preserve error history (stacked data)
      // Do NOT clear recordingInstruction - preserve stacked data
      isCreatedLocally: false,
    });
    return null;
  },
});

/**
 * List users that need mind report import.
 * Returns users that have mindReportStatus as "pending" or null.
 */
export const listPendingMindReports = query({
  args: {},
  returns: v.array(
    v.object({
      _id: v.id("users"),
      _creationTime: v.number(),
      clientCode: v.string(),
      firstName: v.string(),
      lastName: v.optional(v.string()),
      mindReportStatus: v.optional(v.string()),
      mindReportFileLink: v.optional(v.string()),
    })
  ),
  handler: async (ctx) => {
    const allUsers = await ctx.db.query("users").collect();
    return allUsers.filter(
      (user) => !user.mindReportStatus || user.mindReportStatus === "pending"
    );
  },
});

/**
 * Update mind report file link for a user.
 */
export const updateMindReportLink = mutation({
  args: {
    userId: v.id("users"),
    fileLink: v.string(),
  },
  returns: v.null(),
  handler: async (ctx, args) => {
    const user = await ctx.db.get(args.userId);
    if (!user) {
      throw new Error("User not found");
    }

    await ctx.db.patch(args.userId, {
      mindReportFileLink: args.fileLink,
      mindReportStatus: "completed",
    });
    return null;
  },
});

/**
 * Update mind report status for a user.
 */
export const updateMindReportStatus = mutation({
  args: {
    userId: v.id("users"),
    status: v.string(), // "pending", "processing", "completed", "failed"
    errorReason: v.optional(v.string()),
  },
  returns: v.null(),
  handler: async (ctx, args) => {
    const user = await ctx.db.get(args.userId);
    if (!user) {
      throw new Error("User not found");
    }

    await ctx.db.patch(args.userId, {
      mindReportStatus: args.status,
      // Append error reason to existing errorReason array if provided
      errorReason: args.errorReason
        ? [
            ...(Array.isArray(user.errorReason)
              ? user.errorReason
              : user.errorReason
                ? [user.errorReason]
                : []),
            args.errorReason,
          ]
        : user.errorReason,
    });
    return null;
  },
});

/**
 * Trigger mind report import for a specific user.
 * Queues the operation for processing by the local Python sync engine.
 */
export const getMindReport = mutation({
  args: {
    userId: v.id("users"),
  },
  returns: v.object({
    success: v.boolean(),
    message: v.string(),
    operationId: v.optional(v.id("operations")),
  }),
  handler: async (ctx, args) => {
    const user = await ctx.db.get(args.userId);
    if (!user) {
      throw new ConvexError("User not found");
    }

    // Check if already processing or completed
    const currentStatus = user.mindReportStatus;
    if (currentStatus === "processing") {
      return {
        success: false,
        message: "Mind report import is already in progress for this user",
        operationId: undefined,
      };
    }

    if (currentStatus === "completed" && user.mindReportFileLink) {
      return {
        success: false,
        message: "Mind report already exists for this user",
        operationId: undefined,
      };
    }

    // Queue the operation using internal mutation
    try {
      const operationId = await ctx.runMutation(
        internal.operations.queueOperation,
        {
          operationType: "get_mind_report",
          userId: args.userId,
          priority: 0, // Normal priority
        }
      );

      console.log(
        `[getMindReport] Queued operation ${operationId} for user ${user.firstName} (${user.clientCode})`
      );

      return {
        success: true,
        message: `Mind report import queued for user ${user.firstName} (${user.clientCode})`,
        operationId: operationId,
      };
    } catch (error: any) {
      console.error(`[getMindReport] Error queueing operation:`, error);
      if (error.message?.includes("already queued")) {
        return {
          success: false,
          message: error.message,
          operationId: undefined,
        };
      }
      throw new ConvexError(
        `Failed to queue mind report operation: ${error.message}`
      );
    }
  },
});
