import re

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # find broken AutoComplete block (starts with literal backtick r backtick n)
    bad_tag = 'AutoComplete`r`n'
    start = content.find(bad_tag)
    if start == -1:
        print(f'{filepath}: no broken AutoComplete found')
        return

    # find the first "<AutoComplete" which is part of the broken block
    tag_start = content.rfind('<', 0, start) - 1  # get to <
    tag_start = content.rfind('<AutoComplete', 0, start + 20)

    # find end />
    end = content.find('/>', start) + 2

    if tag_start >= 0 and end > start:
        replacement = '''<AutoComplete
            placeholder="?????????"
            options={ECONOMIC_TYPE_OPTIONS.map(t => ({ value: t, label: t }))}
            filterOption={(inputValue, option) =>
              option!.value.toUpperCase().indexOf(inputValue.toUpperCase()) !== -1
            }
            allowClear
          />'''
        content = content[:tag_start] + replacement + content[end:]
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'{filepath}: fixed (chars {tag_start}-{end})')
    else:
        print(f'{filepath}: tag_start={tag_start}, end={end}')

fix_file(r'frontend/src/pages/Enterprise/EnterpriseCreatePage.tsx')
fix_file(r'frontend/src/pages/Enterprise/EnterpriseEditPage.tsx')
