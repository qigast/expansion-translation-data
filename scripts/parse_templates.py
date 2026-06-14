import re

# RegEx to match both _() and COMPOUND_STRING() patterns, capturing the string content inside the parentheses.
STRING_PATTERN = r'(?:_|COMPOUND_STRING)\(\s*(["\'])(.*?)\1\s*\)'

class Template:
    '''
        A class representing a parsed string template, which contains buffers
        and their corresponding value. This is designed to help mass replacing
        the strings in test.battle.unique.txt with the translated versions by
        capturing the buffer values using regular expressions.
    '''
    buffers: list[str]
    buffer_values: list[str]
    raw_string: str

    def __init__(self, template_string: str):
        '''
            Initializes the Template object by parsing the given template string.
        '''
        self.clear()

        self.raw_string = template_string
        self.from_string()

    def clear(self):
        '''
            Clears the Template object.
        '''
        self.buffers = []
        self.buffer_values = []
        self.raw_string = ""

    def from_string(self):
        '''
            Parses the internal raw_string to
            extract buffer names and initialize buffer 
            values as empty strings.
        '''
        i = 0

        while i < len(self.raw_string):
            if self.raw_string[i] == '{':
                # Beginning of a buffer, so we parse it entirely.
                end_index = self.raw_string.find('}', i)
                if end_index == -1:
                    raise ValueError("Unmatched '{' in template string.")
                
                buffer_name = self.raw_string[i+1:end_index]

                self.buffers.append(buffer_name)
                self.buffer_values.append("")  # Placeholder for buffer value
                
                i = end_index + 1
            else:
                # Regular character, we advance by one.
                i += 1

    def __str__(self):
        '''
            Returns a string representation of the Template object.
        '''
        return f"Template(buffers={self.buffers}, buffer_values={self.buffer_values}, raw_string='{self.raw_string}')"

    def __repr__(self):
        '''
            Returns a string representation of the Template object for debugging purposes.
        '''
        return self.__str__()


def parse_from_file(filename: str) -> list[str]:
    '''
        Parses the given file to extract string templates 
        defined using the STRING_PATTERN regular expression.
    '''
    content = ""
    templates: list[str] = []
    
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    matches = re.finditer(STRING_PATTERN, content)
    for match in matches:
        # match.group(0): entire string.
        # match.group(1): quote character.
        # match.group(2): string content.
        templates.append(match.group(2))
    
    return templates

if __name__ == "__main__":
    templates = parse_from_file('en.battle.messages.txt')
    for template in templates:
        print(Template(template))