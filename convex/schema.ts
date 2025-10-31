import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  users: defineTable({
    clientCode: v.string(),
    firstName: v.string(),
    lastName: v.optional(v.string()),
    telephone: v.optional(v.string()),
    email: v.optional(v.string()),
    recordingInstruction: v.optional(v.array(v.string())),
    isCreatedLocally: v.optional(v.boolean()),
    syncStatus: v.optional(v.string()), // Status: "pending", "processing", "completed", "failed", "client_id_mismatch", "delete_failed"
    errorReason: v.optional(v.string()), // Detailed error message
  }).index("by_clientCode", ["clientCode"]),
});
