import { fetchApi } from "./client";

export const AuthService = {
  registerLearner: (data) =>
    fetchApi("/learners/", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  registerGuardian: (data) =>
    fetchApi("/auth/guardian/register", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  loginGuardian: (data) =>
    fetchApi("/auth/guardian/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

export const LearnerService = {
  getProfile: (learnerId) => fetchApi(`/learners/${learnerId}`),
  
  getGamificationProfile: (learnerId) =>
    fetchApi(`/gamification/profile/${learnerId}`),

  getStudyPlan: (learnerId) => fetchApi(`/study-plans/${learnerId}`),
  
  getMastery: (learnerId) => fetchApi(`/learners/${learnerId}/mastery`),

  generateLesson: (data) =>
    fetchApi("/lessons/generate", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  awardXP: (data) =>
    fetchApi("/gamification/award-xp", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

export const ParentService = {
  getLinkedLearners: () => fetchApi("/auth/guardian/linked-learners"),
  
  linkLearner: (learnerId, relationship) =>
    fetchApi("/auth/guardian/link-learner", {
      method: "POST",
      body: JSON.stringify({ learner_id: learnerId, relationship }),
    }),
    
  getReport: (learnerId) => fetchApi(`/parent/learner/${learnerId}/report`),
};

export const DiagnosticService = {
  start: (data) =>
    fetchApi("/diagnostic/start", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  submitResponse: (sessionId, data) =>
    fetchApi(`/diagnostic/session/${sessionId}/respond`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  runLegacy: (data) =>
    fetchApi("/diagnostic/run", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};
