import { request } from './http'
import type { ExportRecord, PdfExportRequest, PngExportRequest, SvgExportRequest } from '@/types/export'

export const exportPng = (payload: PngExportRequest) => request<ExportRecord>({ method: 'POST', url: '/exports/png', data: payload })
export const exportPdf = (payload: PdfExportRequest) => request<ExportRecord>({ method: 'POST', url: '/exports/pdf', data: payload })
export const exportSvg = (payload: SvgExportRequest) => request<ExportRecord>({ method: 'POST', url: '/exports/svg', data: payload })
export const exportCsv = (payload: { project_id?: string; pattern_id?: string; include_waste: boolean }) => request<ExportRecord>({ method: 'POST', url: '/exports/csv', data: payload })
export const exportProject = (payload: { project_id?: string; pattern_id?: string }) => request<ExportRecord>({ method: 'POST', url: '/exports/project', data: payload })
