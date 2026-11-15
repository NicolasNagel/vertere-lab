/* eslint-disable */
// Generated from backend OpenAPI. Run `npm run api:generate`; do not edit.

export type AssignRoleRequest = {
  "role_id": string
}

export type AttendanceCancelRequest = {
  "reason": string
}

export type AttendanceConfirmItemRequest = {
  "exam_id": string
  "quantity"?: number
  "discount_amount"?: number | string | null
  "override_reason"?: string | null
}

export type AttendanceConfirmRequest = {
  "items": Array<AttendanceConfirmItemRequest>
}

export type AttendanceDraftCreateRequest = {
  "clinic_id": string
  "veterinarian_id": string
  "patient_id": string
  "collection_method"?: "HELITO_NICOLAS" | "INTERNAL" | "MARLI" | "COURIER" | "UBER"
  "service_level"?: "NORMAL" | "PLANTAO_NORMAL" | "PLANTAO_ESPECIAL"
  "is_urgent"?: boolean
  "service_date"?: string | null
  "notes"?: string | null
}

export type AttendanceExamRead = {
  "id": string
  "exam_id": string
  "exam_code": string
  "exam_name": string
  "price_base": string | null
  "components": Array<ExamComponentRead>
  "quantity": number
  "discount_amount": string | null
  "surcharge_amount": string | null
  "total_amount": string | null
  "override_reason": string | null
  "status": "ACTIVE" | "CANCELLED"
}

export type AttendanceHistoryImportResponse = {
  "batch_id": string
  "status": "STAGED" | "DRY_RUN_DONE" | "COMMITTED"
  "imported_count": number
  "skipped_existing_count": number
  "rejected_count": number
  "imported_grand_total": string
  "exceptions": Array<ImportRowExceptionRead>
}

export type AttendanceItemEditRequest = {
  "item_id"?: string | null
  "exam_id"?: string | null
  "quantity"?: number
  "discount_amount"?: number | string | null
  "override_reason"?: string | null
}

export type AttendanceItemsUpdateRequest = {
  "row_version": number
  "reason": string
  "items": Array<AttendanceItemEditRequest>
}

export type AttendanceListResponse = {
  "items": Array<AttendanceRead>
  "total": number
  "page": number
  "page_size": number
}

export type AttendancePreviewResponse = {
  "attendance_id": string
  "clinic_id": string
  "veterinarian_id": string
  "patient_id": string
  "collection_method": "HELITO_NICOLAS" | "INTERNAL" | "MARLI" | "COURIER" | "UBER"
  "service_level": "NORMAL" | "PLANTAO_NORMAL" | "PLANTAO_ESPECIAL"
  "service_date": string
  "items": Array<AttendanceExamRead>
  "subtotal": string | null
  "discount_total": string | null
  "surcharge_total": string | null
  "on_call_fee": string | null
  "is_urgent": boolean
  "urgency_fee": string | null
  "clinic_fee": string | null
  "fee_lines": Array<FeeLineRead>
  "grand_total": string | null
}

export type AttendanceRead = {
  "id": string
  "clinic_id": string
  "veterinarian_id": string
  "patient_id": string
  "collection_method": "HELITO_NICOLAS" | "INTERNAL" | "MARLI" | "COURIER" | "UBER"
  "service_level": "NORMAL" | "PLANTAO_NORMAL" | "PLANTAO_ESPECIAL"
  "service_date": string | null
  "notes": string | null
  "status": "DRAFT" | "CONFIRMED" | "IN_PROGRESS" | "COMPLETED" | "CANCELLED" | "ON_HOLD"
  "items": Array<AttendanceExamRead>
  "billing_competence": string | null
  "subtotal": string | null
  "discount_total": string | null
  "surcharge_total": string | null
  "on_call_fee": string | null
  "is_urgent": boolean
  "urgency_fee": string | null
  "clinic_fee": string | null
  "fee_lines": Array<FeeLineRead>
  "grand_total": string | null
  "protocol_number": string | null
  "cancel_reason": string | null
  "created_at": string
  "updated_at": string
  "row_version": number
}

export type AttendanceStatus = "DRAFT" | "CONFIRMED" | "IN_PROGRESS" | "COMPLETED" | "CANCELLED" | "ON_HOLD"

export type AttendanceStatusCountsResponse = {
  "total": number
  "by_status": Record<string, unknown>
  "billed_total": string | null
}

export type AttendanceTimelineEntryRead = {
  "id": string
  "occurred_at": string
  "actor_user_id": string | null
  "actor_name"?: string | null
  "action": string
  "before_state": Record<string, unknown> | null
  "after_state": Record<string, unknown> | null
  "reason": string | null
}

export type AttendanceTimelineResponse = {
  "items": Array<AttendanceTimelineEntryRead>
  "total": number
  "page": number
  "page_size": number
}

export type AttendanceUpdateRequest = {
  "row_version": number
  "clinic_id"?: string | null
  "veterinarian_id"?: string | null
  "patient_id"?: string | null
  "collection_method"?: "HELITO_NICOLAS" | "INTERNAL" | "MARLI" | "COURIER" | "UBER" | null
  "service_level"?: "NORMAL" | "PLANTAO_NORMAL" | "PLANTAO_ESPECIAL" | null
  "is_urgent"?: boolean | null
  "service_date"?: string | null
  "notes"?: string | null
  "reason"?: string | null
}

export type AuthResponse = {
  "user": UserPublicRead
  "permissions": Array<string>
}

export type Body_import_exams_api_v1_exams_import_post = {
  "file": string
}

export type Body_stage_price_table_pdf_api_v1_imports_price_table_stage_post = {
  "file": string
}

export type Body_stage_spreadsheet_api_v1_imports_spreadsheet_stage_post = {
  "file": string
}

export type CepAddressRead = {
  "zip_code": string
  "street": string | null
  "neighborhood": string | null
  "city": string | null
  "state": string | null
}

export type ClinicCreateRequest = {
  "name": string
  "tax_id"?: string | null
  "phone"?: string | null
  "email"?: string | null
  "address_zip_code"?: string | null
  "address_street"?: string | null
  "address_number"?: string | null
  "address_neighborhood"?: string | null
  "address_city"?: string | null
  "address_state"?: string | null
  "address_complement"?: string | null
  "notes"?: string | null
}

export type ClinicDetailRead = {
  "id": string
  "name": string
  "tax_id": string | null
  "phone": string | null
  "email": string | null
  "status": "ACTIVE" | "INACTIVE" | "DELINQUENT" | "SPECIAL"
  "address_zip_code": string | null
  "address_street": string | null
  "address_number": string | null
  "address_neighborhood": string | null
  "address_city": string | null
  "address_state": string | null
  "address_complement": string | null
  "notes": string | null
  "created_at": string
  "updated_at": string
  "row_version": number
  "veterinarians": Array<ClinicLinkedVeterinarian>
}

export type ClinicFeeRuleCreateRequest = {
  "clinic_id": string
  "name": string
  "fee_amount": number | string
  "valid_from": string
  "valid_to"?: string | null
  "reason": string
}

export type ClinicFeeRuleListResponse = {
  "items": Array<ClinicFeeRuleRead>
}

export type ClinicFeeRuleRead = {
  "id": string
  "clinic_id": string
  "name": string
  "fee_amount": string
  "valid_from": string
  "valid_to": string | null
  "is_active": boolean
  "updated_at": string
  "row_version": number
}

export type ClinicFeeRuleUpdateRequest = {
  "name": string
  "fee_amount": number | string
  "valid_from": string
  "valid_to"?: string | null
  "is_active": boolean
  "reason": string
  "expected_row_version": number
}

export type ClinicLinkedVeterinarian = {
  "veterinarian_id": string
  "veterinarian_name": string
  "crmv": string
  "primary_clinic": boolean
}

export type ClinicListResponse = {
  "items": Array<ClinicRead>
  "total": number
  "page": number
  "page_size": number
}

export type ClinicRead = {
  "id": string
  "name": string
  "tax_id": string | null
  "phone": string | null
  "email": string | null
  "status": "ACTIVE" | "INACTIVE" | "DELINQUENT" | "SPECIAL"
  "address_zip_code": string | null
  "address_street": string | null
  "address_number": string | null
  "address_neighborhood": string | null
  "address_city": string | null
  "address_state": string | null
  "address_complement": string | null
  "notes": string | null
  "created_at": string
  "updated_at": string
  "row_version": number
}

export type ClinicStatus = "ACTIVE" | "INACTIVE" | "DELINQUENT" | "SPECIAL"

export type ClinicUpdateRequest = {
  "name": string
  "tax_id"?: string | null
  "phone"?: string | null
  "email"?: string | null
  "status": "ACTIVE" | "INACTIVE" | "DELINQUENT" | "SPECIAL"
  "address_zip_code"?: string | null
  "address_street"?: string | null
  "address_number"?: string | null
  "address_neighborhood"?: string | null
  "address_city"?: string | null
  "address_state"?: string | null
  "address_complement"?: string | null
  "notes"?: string | null
  "expected_row_version": number
}

export type CloseMonthlyPeriodRequest = {
  "clinic_id": string
  "period_start": string
  "period_end": string
}

export type ClosurePreviewBlockedItemRead = {
  "attendance_id": string
  "attendance_exam_id": string
  "protocol_number": string | null
  "patient_name": string
  "exam_name": string
  "total_amount": string
  "reason": string
}

export type ClosurePreviewItemRead = {
  "attendance_id": string
  "attendance_exam_id": string
  "protocol_number": string | null
  "patient_name": string
  "exam_name": string
  "service_level": string
  "exam_category": string
  "total_amount": string
}

export type ClosurePreviewResponse = {
  "clinic_id": string
  "competence_year": number
  "competence_month": number
  "period_start": string
  "period_end": string
  "attendance_count": number
  "cancelled_attendance_count": number
  "item_count": number
  "subtotal": string
  "discount_total": string
  "surcharge_total": string
  "on_call_fee_total": string
  "grand_total": string
  "eligible_items": Array<ClosurePreviewItemRead>
  "blocked_items": Array<ClosurePreviewBlockedItemRead>
  "generated_at": string
}

export type ExamCategoryActiveListResponse = {
  "items": Array<ExamCategoryRead>
}

export type ExamCategoryCreateRequest = {
  "name": string
}

export type ExamCategoryListResponse = {
  "items": Array<ExamCategoryRead>
  "total": number
  "page": number
  "page_size": number
}

export type ExamCategoryRead = {
  "id": string
  "name": string
  "status": "ACTIVE" | "INACTIVE"
  "created_at": string
  "updated_at": string
  "row_version": number
}

export type ExamCategoryStatus = "ACTIVE" | "INACTIVE"

export type ExamCategoryUpdateRequest = {
  "name": string
  "status": "ACTIVE" | "INACTIVE"
  "expected_row_version": number
}

export type ExamComponentRead = {
  "code": string
  "name": string
}

export type ExamCreateRequest = {
  "name": string
  "category_id": string
  "price_base": number | string
  "description"?: string | null
  "species_ids": Array<string>
  "component_exam_ids"?: Array<string>
}

export type ExamImportResponse = {
  "imported_count": number
  "errors": Array<ExamImportRowErrorRead>
}

export type ExamImportRowErrorRead = {
  "line": number
  "message": string
}

export type ExamListResponse = {
  "items": Array<ExamRead>
  "total": number
  "page": number
  "page_size": number
}

export type ExamRead = {
  "id": string
  "code": string
  "name": string
  "category_id": string
  "description": string | null
  "species_ids": Array<string>
  "component_exam_ids": Array<string>
  "is_panel": boolean
  "status": "ACTIVE" | "INACTIVE"
  "created_at": string
  "updated_at": string
  "row_version": number
  "price_base": string | null
  "price_valid_from": string | null
  "price_valid_to": string | null
}

export type ExamStatus = "ACTIVE" | "INACTIVE"

export type ExamUpdateRequest = {
  "name": string
  "category_id": string
  "price_base"?: number | string | null
  "description"?: string | null
  "species_ids": Array<string>
  "component_exam_ids"?: Array<string>
  "status": "ACTIVE" | "INACTIVE"
  "expected_row_version": number
  "reason"?: string | null
}

export type FeeLineRead = {
  "kind": "PLANTAO" | "URGENCIA" | "CLINICA"
  "label": string
  "amount": string | null
  "rule_id"?: string | null
}

export type FinancialAdjustmentCreateRequest = {
  "monthly_closure_item_id"?: string | null
  "kind": string
  "amount": number | string
  "reason": string
}

export type FinancialAdjustmentRead = {
  "id": string
  "monthly_closure_id": string
  "monthly_closure_item_id": string | null
  "kind": string
  "amount": string
  "reason": string
  "created_by": string | null
  "created_at": string
}

export type HealthResponse = {
  "status": string
}

export type HTTPValidationError = {
  "detail"?: Array<ValidationError>
}

export type ImportBatchRead = {
  "id": string
  "source_filename": string
  "checksum_sha256": string
  "status": "STAGED" | "DRY_RUN_DONE" | "COMMITTED"
  "created_at": string
}

export type ImportClinicsResponse = {
  "imported_count": number
  "skipped_existing_count": number
  "exceptions": Array<ImportRowExceptionRead>
}

export type ImportExamCategoriesResponse = {
  "imported_count": number
  "skipped_existing_count": number
}

export type ImportExamsFromHistoryResponse = {
  "imported_count": number
  "skipped_existing_count": number
  "exceptions": Array<ImportRowExceptionRead>
}

export type ImportExceptionRead = {
  "phase": string
  "source_row_number": number
  "message": string
  "created_at": string
}

export type ImportExceptionsListResponse = {
  "batch_id": string
  "exceptions": Array<ImportExceptionRead>
}

export type ImportPatientsResponse = {
  "imported_count": number
  "skipped_existing_count": number
  "exceptions": Array<ImportRowExceptionRead>
}

export type ImportPipelineResponse = {
  "batch_id": string
  "status": "STAGED" | "DRY_RUN_DONE" | "COMMITTED"
  "phases": Array<PipelinePhaseRead>
  "total_imported_count": number
  "total_exceptions_count": number
}

export type ImportRowExceptionRead = {
  "source_row_number": number
  "message": string
}

export type ImportVeterinariansResponse = {
  "imported_count": number
  "skipped_existing_count": number
  "exceptions": Array<ImportRowExceptionRead>
}

export type LinkVeterinarianClinicsResponse = {
  "links_created_count": number
  "exceptions": Array<ImportRowExceptionRead>
}

export type LoginRequest = {
  "login": string
  "password": string
  "remember_me"?: boolean
}

export type MonthlyClosureItemRead = {
  "id": string
  "attendance_id": string
  "attendance_exam_id": string
  "protocol_number": string | null
  "patient_name": string
  "exam_name": string
  "price_base": string
  "quantity": number
  "discount_amount": string
  "surcharge_amount": string
  "total_amount": string
  "service_level"?: string | null
  "exam_category"?: string | null
}

export type MonthlyClosureListResponse = {
  "items": Array<MonthlyClosureSummaryRead>
  "total": number
  "page": number
  "page_size": number
}

export type MonthlyClosureRead = {
  "id": string
  "clinic_id": string
  "competence_year": number
  "competence_month": number
  "period_start": string
  "period_end": string
  "status": "CLOSED" | "REOPENED"
  "item_count": number
  "subtotal": string
  "discount_total": string
  "surcharge_total": string
  "on_call_fee_total": string
  "grand_total": string
  "generated_by": string | null
  "closed_by": string | null
  "generated_at": string
  "closed_at": string
  "reopened_at": string | null
  "version": number
  "items": Array<MonthlyClosureItemRead>
  "adjustments"?: Array<FinancialAdjustmentRead>
}

export type MonthlyClosureSummaryRead = {
  "id": string
  "clinic_id": string
  "competence_year": number
  "competence_month": number
  "period_start": string
  "period_end": string
  "status": "CLOSED" | "REOPENED"
  "item_count": number
  "grand_total": string
  "closed_by": string | null
  "closed_at": string
  "version": number
}

export type OnCallFeeSettingListResponse = {
  "items": Array<OnCallFeeSettingRead>
}

export type OnCallFeeSettingRead = {
  "id": string
  "service_level": "PLANTAO_NORMAL" | "PLANTAO_ESPECIAL"
  "fee_amount": string
  "schedule_label": string
  "weekdays": Array<number>
  "start_time": string | null
  "end_time": string | null
  "updated_at": string
  "row_version": number
}

export type OnCallFeeSettingUpdateRequest = {
  "fee_amount": number | string
  "weekdays"?: Array<number>
  "start_time"?: string | null
  "end_time"?: string | null
  "reason": string
  "expected_row_version": number
}

export type PatientCreateRequest = {
  "clinic_id": string
  "name": string
  "species_id": string
  "sex": "MALE" | "FEMALE"
  "breed"?: string | null
  "age_description"?: string | null
  "owner_name": string
  "owner_phone"?: string | null
  "owner_document"?: string | null
  "notes"?: string | null
  "age_value"?: number | null
  "age_unit"?: "YEARS" | "MONTHS" | null
}

export type PatientListResponse = {
  "items": Array<PatientRead>
  "total": number
  "page": number
  "page_size": number
}

export type PatientRead = {
  "id": string
  "clinic_id": string | null
  "name": string
  "species_id": string
  "sex": "MALE" | "FEMALE"
  "breed": string | null
  "age_description": string | null
  "owner_name": string
  "owner_phone": string | null
  "owner_document": string | null
  "status": "ACTIVE" | "INACTIVE"
  "notes": string | null
  "created_at": string
  "updated_at": string
  "row_version": number
  "age_value": number | null
  "age_unit": "YEARS" | "MONTHS" | null
  "age_recorded_on": string | null
}

export type PatientStatus = "ACTIVE" | "INACTIVE"

export type PatientUpdateRequest = {
  "name": string
  "species_id": string
  "sex": "MALE" | "FEMALE"
  "breed"?: string | null
  "age_description"?: string | null
  "owner_name": string
  "owner_phone"?: string | null
  "owner_document"?: string | null
  "status": "ACTIVE" | "INACTIVE"
  "notes"?: string | null
  "expected_row_version": number
  "clinic_id"?: string | null
  "age_value"?: number | null
  "age_unit"?: "YEARS" | "MONTHS" | null
}

export type PermissionRead = {
  "id": string
  "code": string
  "description": string
  "master_only": boolean
}

export type PipelinePhaseRead = {
  "phase": string
  "imported_count": number
  "skipped_existing_count": number
  "exceptions": Array<ImportRowExceptionRead>
}

export type PriceTableImportResponse = {
  "batch_id": string
  "status": "STAGED" | "DRY_RUN_DONE" | "COMMITTED"
  "imported_count": number
  "skipped_existing_count": number
  "exceptions": Array<ImportRowExceptionRead>
}

export type PriceTablePdfStageResponse = {
  "batch": ImportBatchRead
  "already_staged": boolean
  "item_count": number
  "ignored_surcharge_line_count": number
  "unpaired_line_count": number
}

export type ReopenMonthlyClosureRequest = {
  "reason": string
}

export type RoleCreateRequest = {
  "name": string
  "scope": "GLOBAL" | "LAB" | "CLINIC"
  "description"?: string
  "permissions"?: Array<string>
}

export type RoleListResponse = {
  "items": Array<RoleRead>
  "total": number
  "page": number
  "page_size": number
}

export type RoleRead = {
  "id": string
  "name": string
  "scope": "GLOBAL" | "LAB" | "CLINIC"
  "description": string
  "is_system": boolean
  "permissions": Array<string>
  "row_version": number
}

export type RoleUpdateRequest = {
  "permissions": Array<string>
  "expected_row_version": number
}

export type ServiceLevel = "NORMAL" | "PLANTAO_NORMAL" | "PLANTAO_ESPECIAL"

export type SpeciesListResponse = {
  "items": Array<SpeciesRead>
}

export type SpeciesRead = {
  "id": string
  "name": string
  "created_at": string
}

export type SpreadsheetStageResponse = {
  "batch": ImportBatchRead
  "already_staged": boolean
  "sheet_row_counts": Record<string, unknown>
}

export type UpdateUserAccessRequest = {
  "role_id": string
  "clinic_ids"?: Array<string>
  "expected_row_version": number
}

export type UrgencyFeeSettingRead = {
  "id": string
  "fee_amount": string
  "schedule_label": string
  "weekdays": Array<number>
  "start_time": string | null
  "end_time": string | null
  "updated_at": string
  "row_version": number
}

export type UrgencyFeeSettingUpdateRequest = {
  "fee_amount": number | string
  "weekdays"?: Array<number>
  "start_time"?: string | null
  "end_time"?: string | null
  "reason": string
  "expected_row_version": number
}

export type UserCreateRequest = {
  "email": string
  "full_name": string
  "role_id": string
  "clinic_ids"?: Array<string>
}

export type UserCreateResponse = {
  "user": UserListItemRead
  "temporary_password": string
}

export type UserListItemRead = {
  "id": string
  "email": string
  "full_name": string
  "is_active": boolean
  "role_id": string
  "role_name": string
  "role_scope"?: "GLOBAL" | "LAB" | "CLINIC"
  "clinic_ids"?: Array<string>
  "row_version"?: number
  "created_at": string
}

export type UserListResponse = {
  "items": Array<UserListItemRead>
  "total": number
  "page": number
  "page_size": number
}

export type UserPublicRead = {
  "id": string
  "email": string
  "full_name": string
  "role_id": string
  "role_name": string
  "role_scope"?: "GLOBAL" | "LAB" | "CLINIC"
  "clinic_ids"?: Array<string>
  "row_version"?: number
}

export type ValidationError = {
  "loc": Array<string | number>
  "msg": string
  "type": string
  "input"?: unknown
  "ctx"?: Record<string, unknown>
}

export type VeterinarianCreateRequest = {
  "name": string
  "crmv": string
  "phone"?: string | null
  "email"?: string | null
  "is_autonomous"?: boolean
  "notes"?: string | null
  "clinic_ids"?: Array<string>
  "primary_clinic_id"?: string | null
}

export type VeterinarianDetailRead = {
  "id": string
  "name": string
  "crmv": string
  "phone": string | null
  "email": string | null
  "is_autonomous": boolean
  "status": "ACTIVE" | "INACTIVE"
  "notes": string | null
  "created_at": string
  "updated_at": string
  "row_version": number
  "clinics": Array<VeterinarianLinkedClinic>
}

export type VeterinarianLinkClinicRequest = {
  "clinic_id": string
  "primary"?: boolean
}

export type VeterinarianLinkedClinic = {
  "clinic_id": string
  "clinic_name": string
  "primary_clinic": boolean
}

export type VeterinarianListResponse = {
  "items": Array<VeterinarianRead>
  "total": number
  "page": number
  "page_size": number
}

export type VeterinarianRead = {
  "id": string
  "name": string
  "crmv": string
  "phone": string | null
  "email": string | null
  "is_autonomous": boolean
  "status": "ACTIVE" | "INACTIVE"
  "notes": string | null
  "created_at": string
  "updated_at": string
  "row_version": number
}

export type VeterinarianStatus = "ACTIVE" | "INACTIVE"

export type VeterinarianUpdateRequest = {
  "name": string
  "crmv": string
  "phone"?: string | null
  "email"?: string | null
  "is_autonomous"?: boolean
  "status": "ACTIVE" | "INACTIVE"
  "notes"?: string | null
  "expected_row_version": number
}
