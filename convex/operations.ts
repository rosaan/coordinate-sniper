import { query, mutation, internalMutation } from "./_generated/server";
import { ConvexError, v } from "convex/values";

/**
 * Queue a new operation for processing by the local Python sync engine.
 * This is an internal mutation that can be called from other mutations.
 */
export const queueOperation = internalMutation({
  args: {
    operationType: v.string(), // "create_user", "get_mind_report", etc.
    userId: v.id("users"),
    priority: v.optional(v.number()),
    metadata: v.optional(v.any()),
  },
  returns: v.id("operations"),
  handler: async (ctx, args) => {
    // Verify user exists
    const user = await ctx.db.get(args.userId);
    if (!user) {
      throw new ConvexError("User not found");
    }

    // Check if operation already exists and is pending/processing
    const existingOp = await ctx.db
      .query("operations")
      .withIndex("by_userId", (q) => q.eq("userId", args.userId))
      .filter((q) => q.eq(q.field("operationType"), args.operationType))
      .filter((q) =>
        q.or(
          q.eq(q.field("status"), "pending"),
          q.eq(q.field("status"), "processing")
        )
      )
      .first();

    if (existingOp) {
      throw new ConvexError(
        `Operation ${args.operationType} is already queued or processing for this user`
      );
    }

    // Create operation
    return await ctx.db.insert("operations", {
      operationType: args.operationType,
      userId: args.userId,
      status: "pending",
      priority: args.priority ?? 0,
      metadata: args.metadata,
    });
  },
});

/**
 * List pending operations, ordered by priority (highest first), then creation time.
 */
export const listPendingOperations = query({
  args: {},
  returns: v.array(
    v.object({
      _id: v.id("operations"),
      _creationTime: v.number(),
      operationType: v.string(),
      userId: v.id("users"),
      status: v.string(),
      priority: v.optional(v.number()),
      errorReason: v.optional(v.array(v.string())),
      metadata: v.optional(v.any()),
      user: v.object({
        _id: v.id("users"),
        clientCode: v.string(),
        firstName: v.string(),
        lastName: v.optional(v.string()),
      }),
    })
  ),
  handler: async (ctx) => {
    const operations = await ctx.db
      .query("operations")
      .withIndex("by_status", (q) => q.eq("status", "pending"))
      .collect();

    // Sort by priority (descending), then by creation time (ascending)
    const sorted = operations.sort((a, b) => {
      const priorityDiff = (b.priority ?? 0) - (a.priority ?? 0);
      if (priorityDiff !== 0) return priorityDiff;
      return a._creationTime - b._creationTime;
    });

    // Fetch user data for each operation
    const result = [];
    for (const op of sorted) {
      const user = await ctx.db.get(op.userId);
      if (!user) continue; // Skip if user was deleted

      result.push({
        _id: op._id,
        _creationTime: op._creationTime,
        operationType: op.operationType,
        userId: op.userId,
        status: op.status,
        priority: op.priority,
        errorReason: op.errorReason,
        metadata: op.metadata,
        user: {
          _id: user._id,
          clientCode: user.clientCode,
          firstName: user.firstName,
          lastName: user.lastName,
        },
      });
    }

    return result;
  },
});

/**
 * Update operation status.
 */
export const updateOperationStatus = mutation({
  args: {
    operationId: v.id("operations"),
    status: v.string(), // "processing", "completed", "failed"
    errorReason: v.optional(v.string()),
  },
  returns: v.null(),
  handler: async (ctx, args) => {
    const operation = await ctx.db.get(args.operationId);
    if (!operation) {
      throw new ConvexError("Operation not found");
    }

    // Handle errorReason - stack errors in array
    let updatedErrorReasons: string[] | undefined = undefined;
    if (args.errorReason) {
      const existingErrors = operation.errorReason || [];
      updatedErrorReasons = [...existingErrors, args.errorReason];
    } else {
      updatedErrorReasons = operation.errorReason;
    }

    await ctx.db.patch(args.operationId, {
      status: args.status,
      errorReason: updatedErrorReasons,
    });
    return null;
  },
});

/**
 * Mark operation as completed.
 */
export const completeOperation = mutation({
  args: {
    operationId: v.id("operations"),
  },
  returns: v.null(),
  handler: async (ctx, args) => {
    const operation = await ctx.db.get(args.operationId);
    if (!operation) {
      throw new ConvexError("Operation not found");
    }

    await ctx.db.patch(args.operationId, {
      status: "completed",
    });
    return null;
  },
});

