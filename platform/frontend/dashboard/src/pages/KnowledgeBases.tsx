import React, { useEffect, useState, useRef } from 'react';
import { knowledgeBasesApi } from '../services/api';
import { KnowledgeBase, KBDocument } from '../types';

const statusConfig: Record<string, { label: string; color: string; dot: string }> = {
  processing: { label: 'Processing', color: 'bg-amber-600/20 text-amber-300', dot: 'bg-amber-400' },
  ready: { label: 'Ready', color: 'bg-emerald-600/20 text-emerald-300', dot: 'bg-emerald-400' },
  failed: { label: 'Failed', color: 'bg-red-600/20 text-red-300', dot: 'bg-red-400' },
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function KnowledgeBases() {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedKb, setSelectedKb] = useState<KnowledgeBase | null>(null);
  const [documents, setDocuments] = useState<KBDocument[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [createName, setCreateName] = useState('');
  const [createDesc, setCreateDesc] = useState('');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadKbs = async () => {
    try {
      const data = await knowledgeBasesApi.list();
      setKbs(data);
    } catch {
      setKbs([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadKbs(); }, []);

  const loadDocuments = async (kb: KnowledgeBase) => {
    setSelectedKb(kb);
    setDocsLoading(true);
    try {
      const docs = await knowledgeBasesApi.listDocuments(kb.id);
      setDocuments(docs);
    } catch {
      setDocuments([]);
    } finally {
      setDocsLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!createName.trim()) return;
    setError('');
    try {
      await knowledgeBasesApi.create({ name: createName, description: createDesc });
      setShowCreateModal(false);
      setCreateName('');
      setCreateDesc('');
      await loadKbs();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create knowledge base');
    }
  };

  const handleUpload = async (file: File) => {
    if (!selectedKb) return;
    setUploading(true);
    setError('');
    try {
      await knowledgeBasesApi.uploadDocument(selectedKb.id, file);
      await loadDocuments(selectedKb);
      await loadKbs();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to upload document');
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteDoc = async (docId: string) => {
    if (!selectedKb) return;
    if (!window.confirm('Delete this document and all its chunks?')) return;
    try {
      await knowledgeBasesApi.deleteDocument(selectedKb.id, docId);
      await loadDocuments(selectedKb);
      await loadKbs();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete document');
    }
  };

  const handleDeleteKb = async (kbId: string) => {
    if (!window.confirm('Delete this knowledge base and all documents?')) return;
    try {
      await knowledgeBasesApi.delete(kbId);
      if (selectedKb?.id === kbId) {
        setSelectedKb(null);
        setDocuments([]);
      }
      await loadKbs();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete knowledge base');
    }
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
          <h1 className="text-2xl font-bold text-white">Knowledge Bases</h1>
          <p className="text-gray-400 mt-1">Upload documents to give your AI agents domain knowledge</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-4 py-2.5 rounded-lg bg-vox-600 hover:bg-vox-500 text-white text-sm font-medium transition-colors flex items-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Create Knowledge Base
        </button>
      </div>

      {error && (
        <div className="mb-6 p-4 rounded-lg bg-red-600/10 border border-red-600/20 text-red-300 text-sm">
          {error}
          <button onClick={() => setError('')} className="float-right text-red-400 hover:text-red-300">&times;</button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* KB List */}
        <div className="lg:col-span-1 space-y-3">
          {kbs.length === 0 ? (
            <div className="bg-[#1a1230] rounded-xl p-8 border border-vox-900/50 text-center">
              <div className="w-12 h-12 rounded-full bg-vox-600/20 flex items-center justify-center mx-auto mb-3">
                <svg className="w-6 h-6 text-vox-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
              </div>
              <h3 className="text-white font-medium mb-1">No knowledge bases</h3>
              <p className="text-gray-500 text-xs">Create one and upload documents</p>
            </div>
          ) : (
            kbs.map((kb) => (
              <button
                key={kb.id}
                onClick={() => loadDocuments(kb)}
                className={`w-full text-left p-4 rounded-xl border transition-colors ${
                  selectedKb?.id === kb.id
                    ? 'bg-vox-600/10 border-vox-500/30'
                    : 'bg-[#1a1230] border-vox-900/50 hover:border-vox-500/20'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-white font-medium text-sm truncate">{kb.name}</h3>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDeleteKb(kb.id); }}
                    className="text-gray-600 hover:text-red-400 transition-colors"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
                {kb.description && (
                  <p className="text-gray-500 text-xs mb-2 line-clamp-2">{kb.description}</p>
                )}
                <div className="flex items-center gap-3 text-xs text-gray-400">
                  <span>{kb.document_count} docs</span>
                  <span>{kb.total_chunks} chunks</span>
                </div>
              </button>
            ))
          )}
        </div>

        {/* Document Panel */}
        <div className="lg:col-span-2">
          {selectedKb ? (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50">
              <div className="p-6 border-b border-vox-900/50">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-semibold text-white">{selectedKb.name}</h2>
                    <p className="text-gray-400 text-xs mt-0.5">
                      {selectedKb.embedding_model} &middot; chunk size: {selectedKb.chunk_size}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="file"
                      ref={fileInputRef}
                      className="hidden"
                      accept=".txt,.md,.csv,.pdf,.docx"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleUpload(file);
                        e.target.value = '';
                      }}
                    />
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      disabled={uploading}
                      className="px-4 py-2 rounded-lg bg-vox-600 hover:bg-vox-500 disabled:bg-vox-800 text-white text-sm font-medium transition-colors flex items-center gap-2"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                      </svg>
                      {uploading ? 'Uploading...' : 'Upload Document'}
                    </button>
                  </div>
                </div>
              </div>

              <div className="p-6">
                {docsLoading ? (
                  <div className="flex items-center justify-center h-32">
                    <div className="animate-spin w-6 h-6 border-2 border-vox-500 border-t-transparent rounded-full"></div>
                  </div>
                ) : documents.length === 0 ? (
                  <div className="text-center py-12">
                    <p className="text-gray-400 text-sm mb-2">No documents yet</p>
                    <p className="text-gray-600 text-xs">Upload .txt, .md, .csv, .pdf, or .docx files</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {documents.map((doc) => {
                      const st = statusConfig[doc.status] || statusConfig.processing;
                      return (
                        <div key={doc.id} className="flex items-center justify-between p-3 rounded-lg bg-[#0f0a1e] border border-vox-900/30">
                          <div className="flex items-center gap-3 flex-1 min-w-0">
                            <div className="w-8 h-8 rounded-lg bg-vox-600/10 flex items-center justify-center flex-shrink-0">
                              <svg className="w-4 h-4 text-vox-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                              </svg>
                            </div>
                            <div className="min-w-0">
                              <p className="text-white text-sm font-medium truncate">{doc.filename}</p>
                              <p className="text-gray-500 text-xs">
                                {formatBytes(doc.file_size_bytes)}
                                {doc.chunk_count > 0 && ` \u00b7 ${doc.chunk_count} chunks`}
                                {doc.error_message && ` \u00b7 ${doc.error_message}`}
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-3">
                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${st.color}`}>
                              <span className={`w-1.5 h-1.5 rounded-full ${st.dot}`}></span>
                              {st.label}
                            </span>
                            <button
                              onClick={() => handleDeleteDoc(doc.id)}
                              className="text-gray-600 hover:text-red-400 transition-colors p-1"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                              </svg>
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-[#1a1230] rounded-xl border border-vox-900/50 p-12 text-center">
              <p className="text-gray-400 text-sm">Select a knowledge base to view and manage documents</p>
            </div>
          )}
        </div>
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[#1a1230] rounded-2xl border border-vox-900/50 w-full max-w-md mx-4">
            <div className="p-6 border-b border-vox-900/50">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-white">Create Knowledge Base</h2>
                <button onClick={() => setShowCreateModal(false)} className="text-gray-400 hover:text-white">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">Name</label>
                <input
                  type="text"
                  value={createName}
                  onChange={(e) => setCreateName(e.target.value)}
                  placeholder="e.g. Product FAQ, Support Docs"
                  className="w-full px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm placeholder-gray-600 focus:border-vox-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">Description</label>
                <textarea
                  value={createDesc}
                  onChange={(e) => setCreateDesc(e.target.value)}
                  placeholder="What kind of knowledge does this contain?"
                  rows={3}
                  className="w-full px-3 py-2 rounded-lg bg-[#0f0a1e] border border-vox-900/50 text-white text-sm placeholder-gray-600 focus:border-vox-500 focus:outline-none resize-none"
                />
              </div>
              <button
                onClick={handleCreate}
                disabled={!createName.trim()}
                className="w-full px-4 py-2.5 rounded-lg bg-vox-600 hover:bg-vox-500 disabled:bg-vox-800 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
