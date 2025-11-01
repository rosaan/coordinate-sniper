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
    syncStatus: v.optional(v.string()), // Status: "pending", "processing", "completed", "failed", "client_id_mismatch", "delete_failed", "mysql_error_deleted", "clipboard_copy_failed"
    errorReason: v.optional(v.array(v.string())), // Array of error messages (stacks errors for history)
    mindReportFileLink: v.optional(v.string()), // Link to uploaded mind report PDF file
    mindReportStatus: v.optional(v.string()), // Status: "pending", "processing", "completed", "failed"
  }).index("by_clientCode", ["clientCode"]),

  operations: defineTable({
    operationType: v.string(), // "create_user", "get_mind_report", etc.
    userId: v.id("users"),
    status: v.string(), // "pending", "processing", "completed", "failed"
    priority: v.optional(v.number()), // Higher number = higher priority (default: 0)
    errorReason: v.optional(v.array(v.string())), // Array of error messages
    metadata: v.optional(v.any()), // Additional operation-specific data
  })
    .index("by_status", ["status"])
    .index("by_userId", ["userId"])
    .index("by_status_priority", ["status", "priority"]),
});
