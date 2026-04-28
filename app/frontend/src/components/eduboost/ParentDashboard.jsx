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
  const [activeReport, setActiveReport] = useState(null);
  const [showReportModal, setShowReportModal] = useState(false);

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
    setLoading(true);
    try {
      const report = await ParentService.getReport(learnerId);
      setActiveReport(report);
      setShowReportModal(true);
    } catch (err) {
      alert("Failed to generate report: " + err.message);
    } finally {
      setLoading(false);
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
                <Card key={l.learner_id} className="p-6 bg-[var(--surface2)]/60 backdrop-blur-md shadow-2xl border border-[var(--border)] hover:border-[var(--blue)]/30 transition-all duration-300">
                  <div className="flex items-center gap-4 mb-4">
                    <div className="w-12 h-12 bg-gradient-to-br from-[var(--gold)] to-[var(--orange)] rounded-full flex items-center justify-center text-2xl shadow-[0_0_15px_rgba(255,215,0,0.3)]">🦁</div>
                    <div>
                      <h3 className="font-bold text-white">Grade {l.grade} Learner</h3>
                      <p className="text-[10px] text-[var(--muted)] font-mono">ID: {l.learner_id.substring(0, 8)}...</p>
                    </div>
                    <div className="ml-auto">
                      {l.is_verified ? (
                        <span className="bg-green-100 text-green-700 text-[10px] px-2 py-1 rounded-full font-bold">VERIFIED</span>
                      ) : (
                        <span className="bg-yellow-100 text-yellow-700 text-[10px] px-2 py-1 rounded-full font-bold">PENDING</span>
                      )}
                    </div>
                  </div>

                  <div className="space-y-4 mb-6">
                    <div className="bg-[var(--bg)]/50 p-4 rounded-xl border border-[var(--border)]">
                      <div className="flex justify-between items-end mb-2">
                        <div className="text-[10px] text-[var(--muted)] font-bold uppercase tracking-wider">Level {(Math.floor(l.total_xp / 100)) + 1} Progress</div>
                        <div className="text-xs font-bold text-[var(--blue)]">{l.total_xp % 100}/100 XP</div>
                      </div>
                      <div className="h-2 w-full bg-[var(--surface2)] rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-gradient-to-r from-[var(--blue)] to-[var(--purple)] transition-all duration-1000"
                          style={{ width: `${l.total_xp % 100}%` }}
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div className="bg-[var(--surface2)]/40 p-3 rounded-xl border border-[var(--border)] text-center">
                        <div className="text-[10px] text-[var(--muted)] font-bold uppercase">Total XP</div>
                        <div className="text-lg font-black text-[var(--gold)]">{l.total_xp}</div>
                      </div>
                      <div className="bg-[var(--surface2)]/40 p-3 rounded-xl border border-[var(--border)] text-center">
                        <div className="text-[10px] text-[var(--muted)] font-bold uppercase">Streak</div>
                        <div className="text-lg font-black text-[var(--orange)]">{l.streak_days} days</div>
                      </div>
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
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
          <Card className="w-full max-w-md p-8 bg-[var(--surface)] border-[var(--border)] shadow-[0_20px_50px_rgba(0,0,0,0.5)]">
            <h2 className="text-2xl font-['Baloo_2'] font-bold mb-2 text-white">Link Learner Profile</h2>
            <p className="text-[var(--muted)] text-sm mb-8">Enter the Learner Pseudonym ID from your child's app dashboard.</p>
            
            <form onSubmit={handleLinkLearner}>
              <div className="mb-6">
                <label className="block text-sm font-bold text-blue-100 mb-2">Learner Pseudonym ID</label>
                <input
                   type="text"
                   required
                   placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000"
                   className="w-full bg-[var(--bg)] border-2 border-[var(--border)] rounded-xl p-4 text-white outline-none focus:border-[var(--gold)] transition-all font-mono text-sm"
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

      {showReportModal && activeReport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/90 backdrop-blur-xl overflow-y-auto">
          <div className="w-full max-w-3xl my-8">
            <Card className="p-0 bg-[var(--surface)] border-[var(--border)] shadow-2xl overflow-hidden">
              <div className="bg-gradient-to-r from-[var(--blue)] to-[var(--purple)] p-8 text-white">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h2 className="text-3xl font-['Baloo_2'] font-bold">Progress Report</h2>
                    <p className="text-blue-100 text-sm">Generated on {new Date(activeReport.report_date).toLocaleDateString()}</p>
                  </div>
                  <button 
                    onClick={() => setShowReportModal(false)}
                    className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center hover:bg-white/30 transition-all"
                  >
                    ✕
                  </button>
                </div>
                <div className="bg-white/10 rounded-xl p-4 backdrop-blur-sm border border-white/10">
                  <p className="text-lg leading-relaxed italic">"{activeReport.summary}"</p>
                </div>
              </div>

              <div className="p-8 space-y-8 max-h-[70vh] overflow-y-auto custom-scrollbar">
                {activeReport.sections && activeReport.sections.map((section, idx) => (
                  <div key={idx} className="border-l-4 border-[var(--blue)] pl-6 py-2">
                    <h4 className="text-xs font-black text-[var(--blue)] uppercase tracking-widest mb-2">{section.title}</h4>
                    <p className="text-white/90 leading-relaxed text-sm whitespace-pre-wrap">{section.content}</p>
                  </div>
                ))}

                <div>
                  <h4 className="text-xs font-black text-[var(--orange)] uppercase tracking-widest mb-4">Mastery Breakdown</h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {activeReport.mastery_snapshot && activeReport.mastery_snapshot.map((s, idx) => (
                      <div key={idx} className="bg-[var(--bg)] p-4 rounded-xl border border-[var(--border)]">
                        <div className="flex justify-between text-xs mb-2">
                          <span className="font-bold text-white">{s.subject_code}</span>
                          <span className="text-[var(--gold)]">{Math.round(s.mastery_score * 100)}%</span>
                        </div>
                        <div className="h-1.5 w-full bg-[var(--surface2)] rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-[var(--gold)]" 
                            style={{ width: `${s.mastery_score * 100}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-[var(--blue)]/10 p-6 rounded-2xl border border-[var(--blue)]/20">
                  <h4 className="text-xs font-black text-[var(--blue)] uppercase tracking-widest mb-4">Recommendations</h4>
                  <ul className="space-y-3">
                    {activeReport.recommendations && activeReport.recommendations.map((rec, idx) => (
                      <li key={idx} className="flex gap-3 text-sm text-blue-100">
                        <span className="text-[var(--blue)]">➔</span>
                        <span>{rec}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              <div className="p-6 border-t border-[var(--border)] bg-[var(--surface2)]/50 flex justify-end">
                <Button onClick={() => setShowReportModal(false)}>Close Report</Button>
              </div>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
