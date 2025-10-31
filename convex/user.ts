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
    })
  ),
  handler: async (ctx) => {
    const allUsers = await ctx.db.query("users").collect();
    // Filter users that haven't been created locally yet
    return allUsers.filter((user) => user.isCreatedLocally !== true);
  },
});

/**
 * Update a user with the recording link and mark as created locally.
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
    await ctx.db.patch(args.userId, {
      recordingInstruction: [args.recordingLink],
      isCreatedLocally: true,
    });
    return null;
  },
});
