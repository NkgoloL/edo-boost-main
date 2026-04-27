"use client";

import React, { useState, useEffect } from "react";
import { ParentService } from "../../lib/api/services";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Stars } from "./EntryScreens";

export function ParentDashboard({ onBack }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [learners, setLearners] = useState([]);
  const [showLinkModal, setShowLinkModal] = useState(false);
  const [linkId, setLinkId] = useState("");
  const [linking, setLinking] = useState(false);

  useEffect(() => {
    fetchLinkedLearners();
  }, []);

  const fetchLinkedLearners = async () => {
    setLoading(true);
    try {
      const res = await ParentService.getLinkedLearners();
      setLearners(res.linked_learners || []);
    } catch (err) {
      setError("Failed to fetch linked learners: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLinkLearner = async (e) => {
    e.preventDefault();
    setLinking(true);
    try {
      await ParentService.linkLearner(linkId, "guardian");
      setShowLinkModal(false);
      setLinkId("");
      fetchLinkedLearners();
    } catch (err) {
      alert("Failed to link learner: " + err.message);
    } finally {
      setLinking(false);
    }
  };

  const handleGenerateReport = async (learnerId) => {
    try {
      const report = await ParentService.getReport(learnerId);
      alert("Summary: " + report.summary);
    } catch (err) {
      alert("Failed to generate report: " + err.message);
    }
  };

  return (
    <div className="screen min-h-screen bg-[var(--bg)] p-6 overflow-y-auto">
      <Stars />
      <div className="relative z-10 max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-['Baloo_2'] text-white">Parent Portal</h1>
            <p className="text-blue-100">Manage your linked learner profiles</p>
          </div>
          <Button variant="secondary" onClick={onBack}>Return to App</Button>
        </div>

        {error && <div className="bg-red-500/20 text-red-200 p-4 rounded-xl mb-6 border border-red-500/30">{error}</div>}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {loading ? (
            <div className="col-span-full py-20 text-center text-blue-200">Loading learners...</div>
          ) : learners.length === 0 ? (
            <Card className="col-span-full p-12 text-center bg-white/10 backdrop-blur border-dashed border-2 border-white/20">
              <div className="text-5xl mb-4">👶</div>
              <h3 className="text-xl font-bold text-white mb-2">No linked learners yet</h3>
              <p className="text-blue-100 mb-6 text-sm">Link your child's learner ID to see their progress.</p>
              <Button onClick={() => setShowLinkModal(true)}>+ Link a Learner</Button>
            </Card>
          ) : (
            <>
              {learners.map((l) => (
                <Card key={l.learner_id} className="p-6 bg-white shadow-xl hover:shadow-2xl transition-all">
                  <div className="flex items-center gap-4 mb-4">
                    <div className="w-12 h-12 bg-[var(--gold)] rounded-full flex items-center justify-center text-2xl">🦁</div>
                    <div>
                      <h3 className="font-bold text-gray-800">Grade {l.grade} Learner</h3>
                      <p className="text-xs text-gray-400">ID: {l.learner_id.substring(0, 8)}...</p>
                    </div>
                    <div className="ml-auto">
                      {l.is_verified ? (
                        <span className="bg-green-100 text-green-700 text-[10px] px-2 py-1 rounded-full font-bold">VERIFIED</span>
                      ) : (
                        <span className="bg-yellow-100 text-yellow-700 text-[10px] px-2 py-1 rounded-full font-bold">PENDING</span>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4 mb-6">
                    <div className="bg-gray-50 p-3 rounded-lg text-center">
                      <div className="text-[10px] text-gray-400 font-bold uppercase">Total XP</div>
                      <div className="text-lg font-bold text-blue-600">{l.total_xp}</div>
                    </div>
                    <div className="bg-gray-50 p-3 rounded-lg text-center">
                      <div className="text-[10px] text-gray-400 font-bold uppercase">Streak</div>
                      <div className="text-lg font-bold text-orange-500">{l.streak_days} days</div>
                    </div>
                  </div>

                  <Button variant="secondary" fullWidth onClick={() => handleGenerateReport(l.learner_id)}>
                    📊 View Progress Report
                  </Button>
                </Card>
              ))}
              <button 
                onClick={() => setShowLinkModal(true)}
                className="flex flex-col items-center justify-center p-6 bg-white/5 border-2 border-dashed border-white/20 rounded-2xl hover:bg-white/10 transition-all text-white"
              >
                <span className="text-3xl mb-2">+</span>
                <span className="font-bold">Link Another Learner</span>
              </button>
            </>
          )}
        </div>
      </div>

      {showLinkModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <Card className="w-full max-w-md p-8 bg-white">
            <h2 className="text-2xl font-bold mb-4">Link Learner Profile</h2>
            <p className="text-gray-500 text-sm mb-6">Enter the Learner Pseudonym ID from your child's app dashboard.</p>
            
            <form onSubmit={handleLinkLearner}>
              <div className="mb-6">
                <label className="block text-sm font-bold text-gray-700 mb-1">Learner ID</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000"
                  className="w-full border-2 border-gray-100 rounded-xl p-4 outline-none focus:border-[var(--gold)]"
                  value={linkId}
                  onChange={(e) => setLinkId(e.target.value)}
                />
              </div>
              
              <div className="flex gap-3">
                <Button variant="secondary" onClick={() => setShowLinkModal(false)} className="flex-1">Cancel</Button>
                <Button type="submit" className="flex-1" disabled={linking || !linkId}>
                  {linking ? "Linking..." : "Link Now"}
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
}
