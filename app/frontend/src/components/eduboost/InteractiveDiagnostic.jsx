"use client";

import React, { useState, useEffect } from "react";
import { DiagnosticService } from "../../lib/api/services";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Stars } from "./EntryScreens";

export function InteractiveDiagnostic({ learner, onComplete, onBack }) {
  const [subject, setSubject] = useState(null);
  const [session, setSession] = useState(null);
  const [currentItem, setCurrentItem] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [completed, setCompleted] = useState(false);
  const [gapReport, setGapReport] = useState(null);
  const [startTime, setStartTime] = useState(null);
  const [questionCount, setQuestionCount] = useState(0);
  const maxQuestions = 20;

  const subjects = [
    { code: "MATH", label: "Mathematics", emoji: "🔢", color: "#FFD700" },
    { code: "ENG", label: "English", emoji: "📚", color: "#4CAF50" },
    { code: "NS", label: "Natural Science", emoji: "🔬", color: "#2196F3" },
    { code: "SS", label: "Social Science", emoji: "🌍", color: "#FF5722" },
    { code: "LIFE", label: "Life Orientation", emoji: "🤝", color: "#9C27B0" },
  ];

  const handleStart = async (subjectCode) => {
    setLoading(true);
    setError("");
    setSubject(subjectCode);
    setQuestionCount(0);
    try {
      const res = await DiagnosticService.start({
        learner_id: learner.id,
        subject_code: subjectCode,
        grade: learner.grade,
        max_questions: maxQuestions,
      });
      setSession(res.session_id);
      setCurrentItem(res.first_item);
      setStartTime(Date.now());
      setQuestionCount(1);
    } catch (err) {
      setError("Failed to start diagnostic: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAnswer = async (option) => {
    if (!currentItem) return;
    setLoading(true);
    const timeTaken = Date.now() - startTime;
    
    const selectedIndex = currentItem.options.indexOf(option);

    try {
      const res = await DiagnosticService.submitResponse(session, {
        item_id: currentItem.item_id,
        selected_index: selectedIndex,
        time_on_task_ms: timeTaken,
      });

      if (res.is_complete) {
        setCompleted(true);
        setGapReport(res.gap_report);
      } else {
        setCurrentItem(res.next_item_data || res.next_item);
        setQuestionCount(prev => prev + 1);
        setStartTime(Date.now());
      }
    } catch (err) {
      setError("Failed to submit response: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  if (completed) {
    const mastery = Math.round(gapReport?.mastery_score * 100);
    return (
      <div className="screen flex items-center justify-center p-4">
        <Stars />
        <Card className="relative z-10 p-8 max-w-2xl w-full bg-white/90 backdrop-blur-xl shadow-2xl border-none rounded-3xl">
          <div className="text-center mb-10">
            <div className="text-7xl mb-6 animate-bounce">🏆</div>
            <h2 className="text-4xl font-['Baloo_2'] text-gray-800 font-bold">Assessment Complete!</h2>
            <p className="text-gray-500 text-lg mt-2">Amazing work, {learner?.nickname}! We've mapped your knowledge.</p>
          </div>

          <div className="bg-gradient-to-br from-blue-50 to-indigo-50 p-8 rounded-3xl mb-10 border border-blue-100 shadow-inner">
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-bold text-blue-900 text-xl">Subject Mastery</h3>
              <div className="text-3xl font-black text-blue-600">{mastery}%</div>
            </div>
            
            <div className="h-4 bg-blue-100 rounded-full overflow-hidden mb-8">
              <div 
                className="h-full bg-blue-500 rounded-full transition-all duration-1000"
                style={{ width: `${mastery}%` }}
              />
            </div>

            <div>
              <p className="text-sm font-bold text-blue-800 mb-3 uppercase tracking-wider">Gap Analysis:</p>
              <div className="flex flex-wrap gap-2">
                {gapReport?.knowledge_gaps?.length > 0 ? (
                  gapReport.knowledge_gaps.map((gap, i) => (
                    <span key={i} className="bg-white/80 px-4 py-2 rounded-2xl text-sm font-semibold border border-blue-200 text-blue-700 shadow-sm">
                      📍 {gap.subject}: Grade {gap.gap_grade} Foundations
                    </span>
                  ))
                ) : (
                  <div className="bg-green-100 text-green-700 px-6 py-3 rounded-2xl font-bold flex items-center gap-2">
                    ✅ You have mastered all current concepts!
                  </div>
                )}
              </div>
            </div>
          </div>

          <Button onClick={() => onComplete(subject, mastery)} fullWidth className="py-5 text-xl rounded-2xl shadow-xl shadow-blue-500/20 bg-blue-600 hover:bg-blue-700">
            Update My Study Plan →
          </Button>
        </Card>
      </div>
    );
  }

  if (currentItem) {
    const progress = (questionCount / maxQuestions) * 100;
    return (
      <div className="screen flex items-center justify-center p-4">
        <Stars />
        <Card className="relative z-10 w-full max-w-2xl p-10 bg-white/95 backdrop-blur shadow-2xl border-none rounded-3xl">
          <div className="mb-8">
             <div className="flex justify-between items-center mb-3">
               <span className="bg-blue-100 text-blue-600 px-4 py-1.5 rounded-full text-xs font-black uppercase tracking-widest">
                 {subject} • Grade {learner?.grade}
               </span>
               <span className="text-gray-400 text-xs font-bold font-mono">
                 Question {questionCount} / {maxQuestions}
               </span>
             </div>
             <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
               <div 
                 className="h-full bg-blue-500 transition-all duration-500"
                 style={{ width: `${progress}%` }}
               />
             </div>
          </div>

          <div className="min-h-[120px] flex items-center mb-10">
            <h3 className="text-2xl md:text-3xl font-bold text-gray-800 leading-tight">
              {currentItem.question_text}
            </h3>
          </div>

          <div className="grid grid-cols-1 gap-4 mb-10">
            {currentItem.options?.map((opt, i) => (
              <button
                key={i}
                disabled={loading}
                onClick={() => handleAnswer(opt)}
                className="group relative text-left p-6 border-2 border-gray-50 rounded-2xl hover:border-blue-400 hover:bg-blue-50 transition-all transform hover:-translate-y-1 active:scale-95 shadow-sm"
              >
                <div className="flex items-center gap-4">
                  <span className="w-10 h-10 flex items-center justify-center rounded-xl bg-gray-50 group-hover:bg-blue-100 text-gray-400 group-hover:text-blue-600 font-bold transition-colors">
                    {String.fromCharCode(65 + i)}
                  </span>
                  <span className="font-bold text-gray-700 text-lg">{opt}</span>
                </div>
              </button>
            ))}
          </div>

          {error && (
            <div className="bg-red-50 text-red-500 p-4 rounded-xl mb-6 text-sm font-medium border border-red-100 flex items-center gap-2">
              ⚠️ {error}
            </div>
          )}

          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2 text-gray-400 text-xs font-bold uppercase tracking-wider">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              Adaptive Engine: {currentItem.difficulty_label || "Standard"}
            </div>
            {loading && (
              <div className="flex items-center gap-2 text-blue-500 font-bold text-sm">
                <span className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                Calculating...
              </div>
            )}
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="screen flex items-center justify-center p-4">
      <Stars />
      <Card className="relative z-10 w-full max-w-lg p-10 bg-white/95 backdrop-blur shadow-2xl border-none rounded-3xl">
        <button onClick={onBack} className="text-gray-400 hover:text-gray-600 mb-8 flex items-center gap-2 font-bold transition-colors">
          ← Back to Dashboard
        </button>
        
        <h2 className="text-4xl font-['Baloo_2'] text-gray-800 mb-2 font-bold">Diagnostic</h2>
        <p className="text-gray-500 mb-10 text-lg">Pick a subject to start your adaptive check-in. This helps us find your knowledge gaps.</p>

        <div className="grid grid-cols-1 gap-4">
          {subjects.map((s) => (
            <button
              key={s.code}
              onClick={() => handleStart(s.code)}
              disabled={loading}
              className="group flex items-center gap-5 p-6 border-2 border-gray-50 rounded-3xl hover:border-blue-400 hover:bg-blue-50 transition-all text-left shadow-sm hover:shadow-md active:scale-95"
            >
              <div 
                className="w-16 h-16 rounded-2xl flex items-center justify-center text-4xl shadow-inner transition-transform group-hover:scale-110"
                style={{ backgroundColor: `${s.color}15` }}
              >
                {s.emoji}
              </div>
              <div>
                <span className="block font-black text-gray-800 text-xl">{s.label}</span>
                <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">Adaptive Assessment</span>
              </div>
              {loading && subject === s.code ? (
                <div className="ml-auto w-6 h-6 border-3 border-blue-500 border-t-transparent rounded-full animate-spin" />
              ) : (
                <div className="ml-auto text-gray-200 group-hover:text-blue-400 transition-colors">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M5 12h14M12 5l7 7-7 7"/>
                  </svg>
                </div>
              )}
            </button>
          ))}
        </div>

        {error && (
          <div className="mt-6 bg-red-50 text-red-500 p-4 rounded-xl text-sm font-medium border border-red-100">
            ⚠️ {error}
          </div>
        )}
      </Card>
    </div>
  );
}
