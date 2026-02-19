import React, { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { qaApi } from '../services/api';
import { QASummary, QAScore } from '../types';

export default function QualityAssurance() {
  const [summary, setSummary] = useState<QASummary | null>(null);
  const [scores, setScores] = useState<QAScore[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [scoring, setScoring] = useState(false);
  const [showFlagged, setShowFlagged] = useState(false);

  const fetchData = async () => {
    const [sumData, scoreData] = await Promise.all([
      qaApi.getSummary().catch(() => null),
      qaApi.listScores({ flagged: showFlagged, limit: 50 }).catch(() => ({ scores: [], total: 0 })),
    ]);
    if (sumData) setSummary(sumData);
    setScores(scoreData.scores);
    setTotal(scoreData.total);
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, [showFlagged]);

  const handleScoreBatch = async () => {
    setScoring(true);
    try {
      const result = await qaApi.scoreBatch(100);
      alert(result.message);
      fetchData();
    } catch {
      alert('Failed to score calls');
    }
    setScoring(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-vox-500 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Quality Assurance</h1>
          <p className="text-gray-400 mt-1">100% automated call scoring — every call analyzed</p>
        </div>
        <button
          onClick={handleScoreBatch}
          disabled={scoring}
          className="px-4 py-2 rounded-lg bg-vox-600 hover:bg-vox-500 text-white text-sm font-medium transition-colors disabled:opacity-50"
        >
          {scoring ? 'Scoring...' : 'Score Recent Calls'}
        </button>
      </div>

      {/* QA KPIs */}
      {summary && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
            <QAKpi label="Calls Scored" value={String(summary.total_scored)} />
            <QAKpi label="Avg Score" value={`${summary.avg_overall}/100`} color={summary.avg_overall >= 70 ? 'text-emerald-400' : summary.avg_overall >= 50 ? 'text-amber-400' : 'text-red-400'} />
            <QAKpi label="Flagged" value={String(summary.flagged_count)} color={summary.flagged_count > 0 ? 'text-red-400' : 'text-emerald-400'} />
            <QAKpi label="PII Detected" value={String(summary.pii_count)} color={summary.pii_count > 0 ? 'text-red-400' : 'text-emerald-400'} />
            <QAKpi label="Angry Callers" value={String(summary.angry_count)} color={summary.angry_count > 0 ? 'text-amber-400' : 'text-emerald-400'} />
          </div>

          {/* Score breakdown + Distribution */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            {/* Individual category scores */}
            <div className="bg-[#1a1230] rounded-xl p-6 border border-vox-900/50">
              <h3 className="text-sm font-medium text-gray-300 mb-4">Average Scores by Category</h3>
              <div className="space-y-4">
                <ScoreBar label="Accuracy" score={summary.avg_accuracy} />
                <ScoreBar label="Tone" score={summary.avg_tone} />
                <ScoreBar label="Resolution" score={summary.avg_resolution} />
                <ScoreBar label="Compliance" score={summary.avg_compliance} />
              </div>
            </div>

            {/* Score distribution chart */}
            <div className="bg-[#1a1230] rounded-xl p-6 border border-vox-900/50">
              <h3 className="text-sm font-medium text-gray-300 mb-4">Score Distribution</h3>
              {summary.score_distribution.length > 0 ? (
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={summary.score_distribution}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#2a2040" />
                      <XAxis dataKey="range" stroke="#6b7280" fontSize={11} />
                      <YAxis stroke="#6b7280" fontSize={11} />
                      <Tooltip contentStyle={{ background: '#1a1230', border: '1px solid #3b0f7a', borderRadius: '8px', color: '#f3f0ff' }} />
                      <Bar dataKey="count" fill="#7c3aed" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="h-56 flex items-center justify-center text-gray-500 text-sm">No scored calls yet</div>
              )}
            </div>
          </div>

          {/* Top flag reasons */}
          {summary.top_flag_reasons.length > 0 && (
            <div className="bg-[#1a1230] rounded-xl p-6 border border-vox-900/50 mb-8">
              <h3 className="text-sm font-medium text-gray-300 mb-4">Top Flag Reasons</h3>
              <div className="space-y-2">
                {summary.top_flag_reasons.map((item) => (
                  <div key={item.reason} className="flex items-center justify-between bg-[#0f0a1e] rounded-lg px-4 py-2.5">
                    <span className="text-sm text-gray-300">{item.reason}</span>
                    <span className="text-sm font-medium text-red-400">{item.count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Scores list */}
      <div className="bg-[#1a1230] rounded-xl border border-vox-900/50">
        <div className="flex items-center justify-between p-6 border-b border-vox-900/30">
          <h3 className="text-sm font-medium text-gray-300">
            {showFlagged ? 'Flagged Calls' : 'Recent QA Scores'} ({total})
          </h3>
          <button
            onClick={() => setShowFlagged(!showFlagged)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              showFlagged ? 'bg-red-600/20 text-red-300' : 'bg-white/5 text-gray-400 hover:text-white'
            }`}
          >
            {showFlagged ? 'Show All' : 'Show Flagged Only'}
          </button>
        </div>

        {scores.length > 0 ? (
          <div className="divide-y divide-vox-900/20">
            {scores.map((score) => (
              <div key={score.id} className="p-4 hover:bg-white/[0.02] transition-colors">
                <div className="flex items-center gap-4">
                  {/* Overall score badge */}
                  <div className={`w-12 h-12 rounded-lg flex items-center justify-center font-bold text-lg ${
                    score.overall_score >= 80 ? 'bg-emerald-600/20 text-emerald-400' :
                    score.overall_score >= 60 ? 'bg-amber-600/20 text-amber-400' :
                    'bg-red-600/20 text-red-400'
                  }`}>
                    {score.overall_score}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-white">Call {score.call_id.slice(0, 8)}...</span>
                      {score.flagged && (
                        <span className="px-1.5 py-0.5 text-[10px] font-medium bg-red-600/20 text-red-300 rounded">FLAGGED</span>
                      )}
                      {score.pii_detected && (
                        <span className="px-1.5 py-0.5 text-[10px] font-medium bg-amber-600/20 text-amber-300 rounded">PII</span>
                      )}
                      {score.angry_caller && (
                        <span className="px-1.5 py-0.5 text-[10px] font-medium bg-orange-600/20 text-orange-300 rounded">ANGRY</span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500 truncate">{score.summary}</p>
                  </div>

                  {/* Individual scores */}
                  <div className="hidden md:flex items-center gap-3">
                    <MiniScore label="ACC" value={score.accuracy_score} />
                    <MiniScore label="TONE" value={score.tone_score} />
                    <MiniScore label="RES" value={score.resolution_score} />
                    <MiniScore label="CMP" value={score.compliance_score} />
                  </div>

                  <span className="text-xs text-gray-600">{new Date(score.created_at).toLocaleDateString()}</span>
                </div>

                {/* Flag reasons */}
                {score.flag_reasons.length > 0 && (
                  <div className="mt-2 ml-16 flex flex-wrap gap-1">
                    {score.flag_reasons.map((reason, i) => (
                      <span key={i} className="px-2 py-0.5 text-[10px] bg-red-600/10 text-red-400 rounded">
                        {reason}
                      </span>
                    ))}
                  </div>
                )}

                {/* Suggestions */}
                {score.improvement_suggestions.length > 0 && (
                  <div className="mt-2 ml-16">
                    {score.improvement_suggestions.map((suggestion, i) => (
                      <p key={i} className="text-xs text-gray-500 mt-0.5">• {suggestion}</p>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-12 text-gray-500 text-sm">
            {showFlagged ? 'No flagged calls — great job!' : 'No QA scores yet. Click "Score Recent Calls" to analyze your calls.'}
          </div>
        )}
      </div>
    </div>
  );
}

function QAKpi({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-[#1a1230] rounded-xl p-4 border border-vox-900/50">
      <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">{label}</p>
      <p className={`text-xl font-bold mt-1 ${color || 'text-white'}`}>{value}</p>
    </div>
  );
}

function ScoreBar({ label, score }: { label: string; score: number }) {
  const color = score >= 70 ? 'bg-emerald-500' : score >= 50 ? 'bg-amber-500' : 'bg-red-500';
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm text-gray-300">{label}</span>
        <span className="text-sm font-medium text-white">{score.toFixed(0)}/100</span>
      </div>
      <div className="h-2 bg-[#0f0a1e] rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}

function MiniScore({ label, value }: { label: string; value: number }) {
  return (
    <div className="text-center">
      <p className={`text-sm font-bold ${
        value >= 70 ? 'text-emerald-400' : value >= 50 ? 'text-amber-400' : 'text-red-400'
      }`}>
        {value}
      </p>
      <p className="text-[9px] text-gray-600 uppercase">{label}</p>
    </div>
  );
}
