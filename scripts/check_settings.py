"""检查 backend settings 是否包含 data_stale_after_hours / scheduler_poll_seconds 等。"""
from pathlib import Path
import re
text = Path('backend/src/configs/settings.py').read_text(encoding='utf-8')
for kw in ['data_stale_after_hours', 'scheduler_poll_seconds', 'sync_cron',
          'sync_timezone', 'demo_reference_date']:
    matches = re.findall(rf'\b{kw}\b', text)
    print(f'  {kw}: {len(matches)} matches')