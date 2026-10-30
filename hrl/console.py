"""Small, immediately flushed console events for the SDK demonstration."""
from datetime import datetime


def event(component, action, message, *, fields=(), level='INFO'):
    sections = {
        'STEP 1/4': 'DOWNLOAD EXISTING KNOWLEDGE',
        'STEP 2/4': 'PREPARE KNOWLEDGE',
        'STEP 3/4': 'UPLOAD KNOWLEDGE',
        'STEP 4/4': 'READ BACK & VERIFY',
    }
    if action in sections:
        title = f' {sections[action]} '
        print('\n' + title.center(80, '━'), flush=True)
    if level == 'ERROR':
        icon = '❌ '
    elif action in ('WRITE OK', 'READ OK', 'VERIFIED', 'PROCESS COMPLETE'):
        icon = '✅ '
    elif action in ('READ', 'WRITE', 'READ-BACK START'):
        icon = '🔄 '
    else:
        icon = ''
    timestamp = datetime.now().astimezone().strftime('%H:%M:%S.%f')[:-3]
    print(f'{timestamp} {level:<5} {component:<10} [{action}] {icon}{message}', flush=True)
    for field in fields:
        print(f'    {field}', flush=True)


def size(byte_count):
    return f'{byte_count / 1024:.2f} KiB ({byte_count:,} bytes)'


def banner(title, detail=None):
    width = 78
    print('\n╔' + '═' * width + '╗', flush=True)
    print('║' + title.center(width) + '║', flush=True)
    if detail:
        print('║' + detail.center(width) + '║', flush=True)
    print('╚' + '═' * width + '╝\n', flush=True)


class DemoStopped(Exception):
    """The presenter declined the next step or input was unavailable."""


def step(number, title, *, interactive=False, total=4, section=None, stop_detail=None, label='STEP'):
    if section:
        print('\n' + f' {section} '.center(80, '━'), flush=True)
    action = f'{label} {number}/{total}'
    event('Demo', action, title)
    if not interactive:
        return
    while True:
        try:
            answer = input(f'\nStart next step? {number}/{total} — {title} [y/N]: ').strip().lower()
        except EOFError:
            answer = 'no'
        if answer in ('yes', 'y'):
            return
        if answer in ('no', 'n', ''):
            detail = stop_detail or ('The upload remains in the bucket and is not verified.' if number == 4 else 'This step did not start.')
            raise DemoStopped(f'Stopped before step {number}/{total}. {detail}')
        print('Please enter yes or no.', flush=True)
