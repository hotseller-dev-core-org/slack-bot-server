from typing import List


def parse_txt_from_blocks(block: dict) -> List[str]:
    """
    Slack 메시지 블록에서 텍스트를 추출하는 함수

    Args:
        block (dict): Slack 메시지 블록

    Returns:
        List[str]: 추출된 텍스트 리스트
    """
    if not block:
        return []

    elements = block.get('elements', [])
    if not elements:
        return []

    texts = []
    for element in elements:
        if element.get('type') == 'text':
            texts.append(element.get('text', ''))

    return texts