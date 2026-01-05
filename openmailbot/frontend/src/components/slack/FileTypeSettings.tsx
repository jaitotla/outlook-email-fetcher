'use client'

import { FileText, Image, FileCheck } from 'lucide-react';
import type { SlackWorkspace } from '@/lib/api/slack';

interface FileTypeSettingsProps {
  fileProcessing: SlackWorkspace['fileProcessing'];
  onChange: (updates: Partial<SlackWorkspace['fileProcessing']>) => void;
}

export default function FileTypeSettings({ fileProcessing, onChange }: FileTypeSettingsProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">File Processing</h3>
      
      <div className="space-y-4">
        {/* Process PDFs */}
        <div className="flex items-start gap-3">
          <input
            type="checkbox"
            id="processPDFs"
            checked={fileProcessing.processPDFs}
            onChange={(e) => onChange({ processPDFs: e.target.checked })}
            className="mt-1 w-4 h-4 text-blue-600 rounded focus:ring-2 focus:ring-blue-600"
          />
          <div className="flex-1">
            <label htmlFor="processPDFs" className="flex items-center gap-2 font-medium text-gray-900 cursor-pointer">
              <FileText className="w-5 h-5 text-red-600" />
              Process PDFs
            </label>
            <p className="text-sm text-gray-600">
              Extract text content from PDF files shared in Slack
            </p>
          </div>
        </div>

        {/* Process Documents */}
        <div className="flex items-start gap-3">
          <input
            type="checkbox"
            id="processDocs"
            checked={fileProcessing.processDocs}
            onChange={(e) => onChange({ processDocs: e.target.checked })}
            className="mt-1 w-4 h-4 text-blue-600 rounded focus:ring-2 focus:ring-blue-600"
          />
          <div className="flex-1">
            <label htmlFor="processDocs" className="flex items-center gap-2 font-medium text-gray-900 cursor-pointer">
              <FileCheck className="w-5 h-5 text-blue-600" />
              Process Documents
            </label>
            <p className="text-sm text-gray-600">
              Extract text from .docx, .txt, and other document formats
            </p>
          </div>
        </div>

        {/* Process Images (OCR) */}
        <div className="flex items-start gap-3">
          <input
            type="checkbox"
            id="processImages"
            checked={fileProcessing.processImages}
            onChange={(e) => onChange({ processImages: e.target.checked })}
            className="mt-1 w-4 h-4 text-blue-600 rounded focus:ring-2 focus:ring-blue-600"
          />
          <div className="flex-1">
            <label htmlFor="processImages" className="flex items-center gap-2 font-medium text-gray-900 cursor-pointer">
              <Image className="w-5 h-5 text-green-600" />
              Process Images (OCR)
            </label>
            <p className="text-sm text-gray-600">
              Use OCR to extract text from images and screenshots
            </p>
          </div>
        </div>

        {/* Max File Size */}
        <div className="pt-4 border-t">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Maximum File Size (MB)
          </label>
          <input
            type="number"
            value={fileProcessing.maxFileSize / 1048576}
            onChange={(e) => onChange({ maxFileSize: (parseInt(e.target.value) || 10) * 1048576 })}
            min="1"
            max="100"
            className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-600"
          />
          <p className="mt-1 text-sm text-gray-500">
            Files larger than this will be skipped
          </p>
        </div>
      </div>
    </div>
  );
}
