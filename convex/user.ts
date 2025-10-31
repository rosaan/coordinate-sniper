import { query, mutation } from "./_generated/server";
import { v } from "convex/values";

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
 */
export const createUser = mutation({
  args: {
    firstName: v.string(),
    lastName: v.optional(v.string()),
    telephone: v.optional(v.string()),
    email: v.optional(v.string()),
    recordingInstruction: v.optional(v.array(v.string())),
  },
  returns: v.id("users"),
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

    return await ctx.db.insert("users", {
      firstName: args.firstName,
      clientCode: clientCode!,
      lastName: args.lastName,
      telephone: args.telephone,
      email: args.email,
      recordingInstruction: args.recordingInstruction,
    });
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
      throw new Error("User not found");
    }

    if (user.syncStatus === "processing") {
      throw new Error("Cannot retry while processing");
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
