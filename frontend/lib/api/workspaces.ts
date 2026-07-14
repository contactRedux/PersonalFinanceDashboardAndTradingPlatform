/**
 * API functions for workspace CRUD.
 * Maps to /api/v1/workspaces backend endpoints.
 */
import { apiRequest } from "./client";

export interface Workspace {
  id: string;
  name: string;
  owner_id: string;
  created_at: string;
}

export interface WorkspaceList {
  workspaces: Workspace[];
}

export async function listWorkspaces(): Promise<WorkspaceList> {
  const workspaces = await apiRequest<Workspace[]>("/workspaces");
  return { workspaces };
}

export async function createWorkspace(name: string): Promise<Workspace> {
  return apiRequest<Workspace>("/workspaces", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function updateWorkspace(
  id: string,
  layout: unknown
): Promise<Workspace> {
  return apiRequest<Workspace>(`/workspaces/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ layout }),
  });
}

export async function inviteMember(
  workspaceId: string,
  userId: string,
  role: string
): Promise<void> {
  await apiRequest<unknown>(`/workspaces/${workspaceId}/members`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId, role }),
  });
}
