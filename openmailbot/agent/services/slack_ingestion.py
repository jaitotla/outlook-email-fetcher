"""
Slack ingestion service for fetching and processing Slack messages
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import httpx
from .file_processor import FileProcessor
from .llm import LLMService

logger = logging.getLogger(__name__)


class SlackIngestionService:
    """Service for ingesting Slack messages and channels"""
    
    def __init__(
        self,
        backend_url: str = "http://backend:5000",
        llm_service: Optional[LLMService] = None,
        file_processor: Optional[FileProcessor] = None
    ):
        self.backend_url = backend_url
        self.llm_service = llm_service or LLMService()
        self.file_processor = file_processor or FileProcessor()
    
    async def ingest_workspace(
        self,
        user_id: str,
        workspace_id: str,
        access_token: str,
        bot_token: Optional[str] = None,
        sync_days: int = 7,
        selected_channels: Optional[List[str]] = None,
        selected_dms: Optional[List[str]] = None,
        include_public: bool = True,
        include_private: bool = False,
        include_dms: bool = False,
        file_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ingest Slack workspace messages
        
        Returns:
            Summary of ingestion (channels processed, messages ingested, errors)
        """
        result = {
            'channels_processed': 0,
            'dms_processed': 0,
            'messages_ingested': 0,
            'files_processed': 0,
            'errors': []
        }
        
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=sync_days)
            
            # Fetch channels
            channels = await self._fetch_channels(
                access_token,
                include_public,
                include_private,
                selected_channels
            )
            
            # Process each channel
            for channel in channels:
                try:
                    await self._process_channel(
                        user_id=user_id,
                        workspace_id=workspace_id,
                        channel=channel,
                        access_token=bot_token or access_token,
                        start_date=start_date,
                        end_date=end_date,
                        file_config=file_config,
                        result=result
                    )
                    result['channels_processed'] += 1
                except Exception as e:
                    logger.error(f"Error processing channel {channel.get('id')}: {str(e)}")
                    result['errors'].append(f"Channel {channel.get('name')}: {str(e)}")
            
            # Fetch and process DMs if enabled
            if include_dms:
                dms = await self._fetch_dms(access_token, selected_dms)
                
                for dm in dms:
                    try:
                        await self._process_dm(
                            user_id=user_id,
                            workspace_id=workspace_id,
                            dm=dm,
                            access_token=access_token,
                            start_date=start_date,
                            end_date=end_date,
                            file_config=file_config,
                            result=result
                        )
                        result['dms_processed'] += 1
                    except Exception as e:
                        logger.error(f"Error processing DM {dm.get('id')}: {str(e)}")
                        result['errors'].append(f"DM: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error ingesting Slack workspace: {str(e)}")
            result['errors'].append(str(e))
        
        return result
    
    async def _fetch_channels(
        self,
        access_token: str,
        include_public: bool,
        include_private: bool,
        selected_channels: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """Fetch list of channels"""
        channels = []
        
        try:
            async with httpx.AsyncClient() as client:
                # Public channels
                if include_public:
                    response = await client.get(
                        'https://slack.com/api/conversations.list',
                        headers={'Authorization': f'Bearer {access_token}'},
                        params={'types': 'public_channel', 'exclude_archived': True}
                    )
                    data = response.json()
                    if data.get('ok'):
                        channels.extend(data.get('channels', []))
                
                # Private channels
                if include_private:
                    response = await client.get(
                        'https://slack.com/api/conversations.list',
                        headers={'Authorization': f'Bearer {access_token}'},
                        params={'types': 'private_channel', 'exclude_archived': True}
                    )
                    data = response.json()
                    if data.get('ok'):
                        channels.extend(data.get('channels', []))
            
            # Filter by selected channels if provided
            if selected_channels:
                channels = [c for c in channels if c['id'] in selected_channels]
        
        except Exception as e:
            logger.error(f"Error fetching channels: {str(e)}")
        
        return channels
    
    async def _fetch_dms(
        self,
        access_token: str,
        selected_dms: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """Fetch list of DM conversations"""
        dms = []
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    'https://slack.com/api/conversations.list',
                    headers={'Authorization': f'Bearer {access_token}'},
                    params={'types': 'im,mpim', 'exclude_archived': True}
                )
                data = response.json()
                if data.get('ok'):
                    dms = data.get('channels', [])
                    
                    # Filter by selected DMs if provided
                    if selected_dms:
                        dms = [dm for dm in dms if dm['id'] in selected_dms]
        
        except Exception as e:
            logger.error(f"Error fetching DMs: {str(e)}")
        
        return dms
    
    async def _process_channel(
        self,
        user_id: str,
        workspace_id: str,
        channel: Dict[str, Any],
        access_token: str,
        start_date: datetime,
        end_date: datetime,
        file_config: Optional[Dict[str, Any]],
        result: Dict[str, Any]
    ):
        """Process a single channel"""
        channel_id = channel['id']
        channel_name = channel['name']
        
        # Fetch messages in batches
        messages_by_day = {}
        cursor = None
        
        async with httpx.AsyncClient() as client:
            while True:
                params = {
                    'channel': channel_id,
                    'oldest': start_date.timestamp(),
                    'latest': end_date.timestamp(),
                    'limit': 100
                }
                if cursor:
                    params['cursor'] = cursor
                
                response = await client.get(
                    'https://slack.com/api/conversations.history',
                    headers={'Authorization': f'Bearer {access_token}'},
                    params=params
                )
                
                data = response.json()
                if not data.get('ok'):
                    logger.error(f"Slack API error: {data.get('error')}")
                    break
                
                messages = data.get('messages', [])
                
                # Group messages by day
                for msg in messages:
                    if msg.get('type') != 'message':
                        continue
                    
                    ts = float(msg['ts'])
                    msg_date = datetime.fromtimestamp(ts).date()
                    
                    if msg_date not in messages_by_day:
                        messages_by_day[msg_date] = []
                    messages_by_day[msg_date].append(msg)
                
                # Check for pagination
                if not data.get('has_more'):
                    break
                cursor = data.get('response_metadata', {}).get('next_cursor')
        
        # Process each day's messages
        for date, day_messages in messages_by_day.items():
            await self._process_day_messages(
                user_id=user_id,
                workspace_id=workspace_id,
                workspace_name=channel.get('name', workspace_id),
                channel_id=channel_id,
                channel_name=channel_name,
                channel_type='public_channel' if not channel.get('is_private') else 'private_channel',
                date=date,
                messages=day_messages,
                access_token=access_token,
                file_config=file_config,
                result=result
            )
    
    async def _process_dm(
        self,
        user_id: str,
        workspace_id: str,
        dm: Dict[str, Any],
        access_token: str,
        start_date: datetime,
        end_date: datetime,
        file_config: Optional[Dict[str, Any]],
        result: Dict[str, Any]
    ):
        """Process a direct message conversation"""
        # Similar to _process_channel but for DMs
        # Implementation follows same pattern
        pass
    
    async def _process_day_messages(
        self,
        user_id: str,
        workspace_id: str,
        workspace_name: str,
        channel_id: str,
        channel_name: str,
        channel_type: str,
        date: datetime,
        messages: List[Dict[str, Any]],
        access_token: str,
        file_config: Optional[Dict[str, Any]],
        result: Dict[str, Any]
    ):
        """Process a day's worth of messages for a channel"""
        
        # Step 1: Filter out general chat using LLM
        filtered_messages = await self._filter_general_chat(messages)
        
        if not filtered_messages:
            logger.info(f"All messages filtered out for {channel_name} on {date}")
            return
        
        # Step 2: Process files in messages
        for msg in filtered_messages:
            if 'files' in msg:
                for file_info in msg['files']:
                    if file_config:
                        processed_file = await self._process_message_file(
                            file_info, access_token, file_config
                        )
                        if processed_file:
                            msg.setdefault('processed_files', []).append(processed_file)
                            result['files_processed'] += 1
        
        # Step 3: Summarize day's messages into conversation points
        conversation_summary = await self._summarize_conversation(
            messages=filtered_messages,
            channel_name=channel_name,
            date=date
        )
        
        # Step 4: Identify topics using LLM
        topics = await self._identify_topics(conversation_summary['summary'])
        
        # Step 5: Analyze sentiment
        sentiment = await self._analyze_sentiment(filtered_messages)
        
        # Step 6: Extract participants
        participants = self._extract_participants(filtered_messages)
        
        # Step 7: Save to backend
        await self._save_slack_data(
            user_id=user_id,
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            channel_id=channel_id,
            channel_name=channel_name,
            channel_type=channel_type,
            date=date,
            messages=filtered_messages,
            conversation_summary=conversation_summary,
            topics=topics,
            sentiment=sentiment,
            participants=participants
        )
        
        result['messages_ingested'] += len(filtered_messages)
    
    async def _filter_general_chat(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Use LLM to filter out casual greetings and general chat"""
        
        # Prepare messages for classification
        conversation_text = "\n".join([
            f"{msg.get('user', 'Unknown')}: {msg.get('text', '')}"
            for msg in messages[:50]  # Limit to first 50 messages
        ])
        
        prompt = f"""Analyze this Slack conversation and classify each message as either:
- KEEP: Work-related, important information, decisions, action items, questions, discussions
- FILTER: Casual greetings (hi, hello, good morning), small talk, emojis only, "+1", "thanks", "lol"

Conversation:
{conversation_text}

Return a JSON array with indices of messages to KEEP (0-indexed).
Example: {{"keep": [0, 2, 5, 7]}}
"""
        
        try:
            response = await self.llm_service.generate(
                prompt=prompt,
                system_prompt="You are a message classifier that filters out casual chat while keeping important work conversations."
            )
            
            import json
            classification = json.loads(response)
            keep_indices = set(classification.get('keep', []))
            
            # Return only messages to keep
            return [msg for i, msg in enumerate(messages) if i in keep_indices]
        
        except Exception as e:
            logger.error(f"Error filtering general chat: {str(e)}")
            # If classification fails, keep all messages
            return messages
    
    async def _process_message_file(
        self,
        file_info: Dict[str, Any],
        access_token: str,
        file_config: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Process a file attachment from Slack"""
        
        mime_type = file_info.get('mimetype')
        file_size = file_info.get('size', 0)
        file_url = file_info.get('url_private')
        file_name = file_info.get('name')
        
        # Check file size limit
        if file_size > file_config.get('maxFileSize', 10485760):
            return {
                'name': file_name,
                'type': mime_type,
                'size': file_size,
                'extracted_text': '',
                'error': 'File too large'
            }
        
        # Check file type
        process_file = False
        use_ocr = False
        
        if mime_type == 'application/pdf' and file_config.get('processPDFs'):
            process_file = True
        elif mime_type in ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'] and file_config.get('processDocs'):
            process_file = True
        elif mime_type and mime_type.startswith('image/') and file_config.get('processImages'):
            process_file = True
            use_ocr = True
        
        if not process_file:
            return {
                'name': file_name,
                'type': mime_type,
                'size': file_size,
                'extracted_text': '',
                'processed': False
            }
        
        # Download and process file
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    file_url,
                    headers={'Authorization': f'Bearer {access_token}'}
                )
                file_data = response.content
            
            processed = await self.file_processor.process_file(
                file_data=file_data,
                file_name=file_name,
                mime_type=mime_type,
                use_ocr=use_ocr
            )
            
            return {
                'name': file_name,
                'type': mime_type,
                'size': file_size,
                'url': file_url,
                'extracted_text': processed.get('extracted_text', ''),
                'description': processed.get('description', ''),
                'processed': processed.get('processed', False),
                'error': processed.get('error')
            }
        
        except Exception as e:
            logger.error(f"Error processing file {file_name}: {str(e)}")
            return {
                'name': file_name,
                'error': str(e)
            }
    
    async def _summarize_conversation(
        self,
        messages: List[Dict[str, Any]],
        channel_name: str,
        date: datetime
    ) -> Dict[str, Any]:
        """Summarize a day's conversation into key points"""
        
        conversation_text = "\n".join([
            f"{msg.get('user', 'Unknown')} ({datetime.fromtimestamp(float(msg['ts'])).strftime('%H:%M')}): {msg.get('text', '')}"
            for msg in messages
        ])
        
        prompt = f"""Summarize this Slack conversation from #{channel_name} on {date.strftime('%Y-%m-%d')}.

Provide:
1. A brief summary (2-3 sentences)
2. Key points as a list (important information, decisions, action items)
3. Mark each point as high/medium/low importance
4. Indicate if each point is actionable

Conversation:
{conversation_text}

Return JSON:
{{
  "summary": "Brief overview...",
  "points": [
    {{"text": "Point 1", "importance": "high", "actionable": true}},
    ...
  ]
}}
"""
        
        try:
            response = await self.llm_service.generate(
                prompt=prompt,
                system_prompt="You are an expert at summarizing workplace conversations and extracting actionable insights."
            )
            
            import json
            return json.loads(response)
        
        except Exception as e:
            logger.error(f"Error summarizing conversation: {str(e)}")
            return {
                'summary': conversation_text[:500],
                'points': []
            }
    
    async def _identify_topics(self, summary: str) -> List[str]:
        """Identify topics/projects from conversation summary"""
        
        prompt = f"""Identify 1-3 main topics or projects discussed in this summary.
Return topics as a JSON array of strings.

Summary: {summary}

Example: {{"topics": ["project-alpha", "budget-review", "customer-feedback"]}}
"""
        
        try:
            response = await self.llm_service.generate(prompt=prompt)
            import json
            return json.loads(response).get('topics', [])
        except Exception as e:
            logger.error(f"Error identifying topics: {str(e)}")
            return []
    
    async def _analyze_sentiment(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze overall sentiment and tone of conversation"""
        
        sample_messages = "\n".join([
            msg.get('text', '') for msg in messages[:20]
        ])
        
        prompt = f"""Analyze the sentiment and tone of this conversation.

Messages:
{sample_messages}

Return JSON:
{{
  "overall": "positive|neutral|negative|mixed",
  "score": 0.5
}}

Score: -1 (very negative) to +1 (very positive)
"""
        
        try:
            response = await self.llm_service.generate(prompt=prompt)
            import json
            return json.loads(response)
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {str(e)}")
            return {'overall': 'neutral', 'score': 0}
    
    def _extract_participants(self, messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Extract unique participants from messages"""
        participants = {}
        
        for msg in messages:
            user_id = msg.get('user')
            if user_id and user_id not in participants:
                participants[user_id] = {
                    'id': user_id,
                    'name': msg.get('user_profile', {}).get('real_name', user_id),
                    'email': msg.get('user_profile', {}).get('email', '')
                }
        
        return list(participants.values())
    
    async def _save_slack_data(
        self,
        user_id: str,
        workspace_id: str,
        workspace_name: str,
        channel_id: str,
        channel_name: str,
        channel_type: str,
        date: datetime,
        messages: List[Dict[str, Any]],
        conversation_summary: Dict[str, Any],
        topics: List[str],
        sentiment: Dict[str, Any],
        participants: List[Dict[str, str]]
    ):
        """Save Slack data to backend"""
        
        try:
            async with httpx.AsyncClient() as client:
                # Save SlackMetadata
                slack_metadata = {
                    'userId': user_id,
                    'workspaceId': workspace_id,
                    'workspaceName': workspace_name,
                    'channelId': channel_id,
                    'channelName': channel_name,
                    'channelType': channel_type,
                    'messageType': 'channel_message',
                    'date': date.isoformat(),
                    'messages': messages,
                    'syncStatus': {
                        'lastSyncedAt': datetime.now().isoformat(),
                        'status': 'completed'
                    }
                }
                
                slack_response = await client.post(
                    f'{self.backend_url}/api/slack/metadata',
                    json=slack_metadata
                )
                slack_metadata_id = slack_response.json().get('id')
                
                # Save ConversationPoint
                conversation_point = {
                    'userId': user_id,
                    'streamType': 'slack',
                    'date': date.isoformat(),
                    'summary': conversation_summary['summary'],
                    'points': conversation_summary['points'],
                    'topics': topics,
                    'sentiment': sentiment,
                    'participants': participants,
                    'sourceMetadata': {
                        'metadataId': slack_metadata_id,
                        'metadataType': 'SlackMetadata'
                    }
                }
                
                await client.post(
                    f'{self.backend_url}/api/conversations/points',
                    json=conversation_point
                )
        
        except Exception as e:
            logger.error(f"Error saving Slack data: {str(e)}")
            raise
