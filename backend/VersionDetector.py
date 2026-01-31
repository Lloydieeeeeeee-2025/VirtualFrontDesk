import re
from typing import Optional, Dict, List
from datetime import datetime


class VersionDetector:
    """Detects and compares document versions based on revision dates in content."""
    
    def __init__(self):
        self.revision_patterns = [
            r'revised\s+(\d{4})\s+edition',
            r'revision[:\s]+(\d{4})',
            r'revised[:\s]+(\d{4})',
            r'updated[:\s]+(\d{4})',
            r'effective[:\s]+(\d{4})',
            r'approved[:\s]+(\d{4})',
            r'(\d{4})[:\s]+edition',
            r'version[:\s]+(\d{4})',
            r'amended[:\s]+(\d{4})',
            r'as\s+of[:\s]+(\d{4})',
            r'(?:january|february|march|april|may|june|july|august|september|october|november|december)[,\s]+\d{1,2}[,\s]+(\d{4})',
            r'\d{1,2}[/-]\d{1,2}[/-](\d{4})',
        ]
        
        # Document type identifiers for content-based grouping
        self.document_type_keywords = {
            'student_handbook': [
                'student handbook', 'student affairs', 'code of conduct', 
                'admission policies', 'grading system', 'enrollment',
                'disciplinary measures', 'higher education department'
            ],
            'student_council': [
                'student council', 'sc constitution', 'council officers',
                'student government', 'sc elections'
            ]
        }
        
        # Program-specific course identifiers - DO NOT GROUP TOGETHER
        self.program_identifiers = {
            'bsit': ['bachelor of science in information technology', 'bsit', 'information technology'],
            'bsba_om': ['operations management', 'bsba om', 'bsba-om'],
            'bsba_fm': ['financial management', 'bsba fm', 'bsba-fm'],
            'bsba_mm': ['marketing management', 'bsba mm', 'bsba-mm'],
            'bsentrep': ['entrepreneurship', 'bsentrep', 'bs entrep'],
            'bsed_math': ['secondary education', 'mathematics', 'bsed math', 'bsed-math'],
            'bsed_english': ['secondary education', 'english', 'bsed english', 'bsed-eng'],
            'beed': ['elementary education', 'beed'],
            'act_network': ['networking', 'act network'],
            'act_data': ['data engineering', 'act data'],
            'act_appdev': ['applications development', 'act app'],
            'tcp': ['teacher certificate program', 'tcp'],
            'shs': ['senior high school', 'shs subjects']
        }
    
    def extract_revision_year(self, content: str) -> Optional[int]:
        """Extract the most recent revision year from document content."""
        if not content:
            return None
        
        content_lower = content.lower()
        found_years = []
        
        for pattern in self.revision_patterns:
            matches = re.finditer(pattern, content_lower, re.IGNORECASE)
            for match in matches:
                try:
                    year = int(match.group(1))
                    if 1900 <= year <= datetime.now().year + 5:
                        found_years.append(year)
                except (ValueError, IndexError):
                    continue
        
        return max(found_years) if found_years else None
    
    def extract_all_revision_info(self, content: str) -> Dict:
        """Extract comprehensive revision information from document."""
        revision_year = self.extract_revision_year(content)
        content_start = content[:2000].lower()
        
        revision_mentions = 0
        if revision_year:
            revision_mentions = len(re.findall(rf'\b{revision_year}\b', content_start))
        
        return {
            'year': revision_year,
            'mentions': revision_mentions,
            'has_revision_info': revision_year is not None
        }
    
    def _detect_program_type(self, content: str, name: str) -> Optional[str]:
        """Detect specific program from course document."""
        content_sample = content[:3000].lower()
        name_lower = name.lower()
        
        for program_key, keywords in self.program_identifiers.items():
            score = 0
            for keyword in keywords:
                if keyword in content_sample:
                    score += 2
                if keyword in name_lower:
                    score += 5
            
            if score >= 5:  # Threshold for program identification
                return program_key
        
        return None
    
    def _detect_document_type(self, content: str, name: str, doc_type: str) -> str:
        """Detect document type from content analysis."""
        content_sample = content[:5000].lower()
        name_lower = name.lower()
        
        # First check if it's a course document
        if doc_type == 'course':
            program = self._detect_program_type(content, name)
            if program:
                return f"course_{program}"  # e.g., "course_bsit"
            return "course_unknown"
        
        # For handbooks, check type
        type_scores = {}
        for doc_type_key, keywords in self.document_type_keywords.items():
            score = 0
            for keyword in keywords:
                score += content_sample.count(keyword) * 2
                if keyword in name_lower:
                    score += 5
            type_scores[doc_type_key] = score
        
        if max(type_scores.values()) > 0:
            detected_type = max(type_scores, key=type_scores.get)
            return detected_type
        
        return 'unknown'
    
    def determine_archive_status(self, documents_data: List[Dict]) -> Dict[str, bool]:
        """
        Determine which documents should be archived based on version supersession.
        
        Returns:
            Dict mapping document_id to archive status (True = archived, False = current)
        """
        archive_status = {}
        grouped_docs = self._group_similar_documents(documents_data)
        
        print(f"\n📊 Grouped {len(documents_data)} documents into {len(grouped_docs)} groups")
        
        for group_key, docs in grouped_docs.items():
            print(f"\n🔍 Analyzing group: {group_key}")
            print(f"   Documents in group: {len(docs)}")
            
            if len(docs) == 1:
                archive_status[docs[0]['id']] = False
                print(f"   ✓ Single document: {docs[0]['id']} (CURRENT)")
            else:
                docs_with_info = []
                
                for doc in docs:
                    revision_info = self.extract_all_revision_info(doc['content'])
                    docs_with_info.append({
                        'id': doc['id'],
                        'name': doc['name'],
                        'year': revision_info['year'] if revision_info['year'] else 0,
                        'mentions': revision_info['mentions'],
                        'updated_at': doc.get('updated_at', ''),
                        'has_revision_info': revision_info['has_revision_info']
                    })
                    
                    print(f"   📄 {doc['id']} ({doc['name']}): year={revision_info['year']}, mentions={revision_info['mentions']}")
                
                docs_with_info.sort(
                    key=lambda x: (
                        x['has_revision_info'],
                        x['year'],
                        x['mentions'],
                        x['updated_at']
                    ),
                    reverse=True
                )
                
                for idx, doc in enumerate(docs_with_info):
                    is_archived = (idx > 0)
                    archive_status[doc['id']] = is_archived
                    
                    status = "ARCHIVED" if is_archived else "CURRENT"
                    print(f"   {'📦' if is_archived else '✓'} {status}: {doc['id']} (Year: {doc['year'] if doc['year'] else 'N/A'})")
        
        return archive_status
    
    def _group_similar_documents(self, documents_data: List[Dict]) -> Dict[str, List[Dict]]:
        """Group documents by detected type from content analysis."""
        groups = {}
        
        for doc in documents_data:
            doc_type = doc.get('type', 'unknown')
            doc_name = doc.get('name', '')
            doc_content = doc.get('content', '')
            
            # Detect document type from content
            detected_type = self._detect_document_type(doc_content, doc_name, doc_type)
            
            # Create group key: data_type_detected_content_type
            group_key = f"{doc_type}_{detected_type}"
            
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(doc)
            
            print(f"   📑 {doc['id']} ({doc_name}) → detected as '{detected_type}'")
        
        return groups
    
    def should_include_archived(self, query: str) -> Dict[str, any]:
        """
        Determine if archived documents should be included based on query.
        
        Returns:
            Dict with search parameters for archived content
        """
        query_lower = query.lower()
        
        year_matches = re.findall(r'\b(19\d{2}|20\d{2})\b', query)
        specific_year = int(year_matches[0]) if year_matches else None
        
        historical_keywords = [
            'last year', 'previous', 'old', 'before', 'was', 'were',
            'history', 'historical', 'past', 'earlier', 'former',
            'previous version', 'old version', 'archived', 'according to the',
            'based on the', 'in the old', 'what was'
        ]
        
        current_keywords = [
            'current', 'now', 'today', 'present', 'latest',
            'this year', 'new', 'updated', 'recent'
        ]
        
        has_historical = any(keyword in query_lower for keyword in historical_keywords)
        has_current = any(keyword in query_lower for keyword in current_keywords)
        
        if specific_year:
            print(f"🔍 Detected specific year in query: {specific_year}")
            return {
                'include_archived': True,
                'archived_only': False,
                'specific_year': specific_year,
                'prefer_year': True
            }
        
        if has_historical and not has_current:
            print(f"🔍 User requesting historical data")
            return {
                'include_archived': True,
                'archived_only': True,
                'specific_year': None,
                'prefer_year': False
            }
        elif has_historical:
            return {
                'include_archived': True,
                'archived_only': False,
                'specific_year': None,
                'prefer_year': False
            }
        else:
            return {
                'include_archived': False,
                'archived_only': False,
                'specific_year': None,
                'prefer_year': False
            }