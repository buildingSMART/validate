from lark import Lark, Transformer
from lark.exceptions import UnexpectedCharacters, UnexpectedEOF, UnexpectedToken


# https://standards.buildingsmart.org/documents/Implementation/ImplementationGuide_IFCHeaderData_Version_1.0.2.pdf
mvd_grammar = r'''
    start: entry+

    entry: "ViewDefinition" "[" simple_value_list "]"   -> view_definition
         | "Comment" "[" comment_text "]" -> comment
         | GENERIC_KEYWORD "[" value_list_set "]" -> dynamic_option

    %declare COMMENT_TEXT  // Ensure Lark treats it with higher priority

    GENERIC_KEYWORD: /[A-Za-z0-9_]+/
    
    simple_value_list: value ("," value)*
    
    value_list_set: value_set (";" value_set)*

    value_set: set_name ":" simple_value_list
    
    set_name: /[A-Za-z0-9_]+/
    
    value: /[A-Za-z0-9 _-]+/
    
    comment_text: /[^\[\]]+/  

    %import common.WS
    %ignore WS
'''


parser = Lark(mvd_grammar, parser='lalr')
class DescriptionTransform(Transformer):
    def __init__(self):
        self.mvd = []
        self.keywords = set()
        self.comments = ""
        self.exchangerequirement = ""
        self.option = ''


    def view_definition(self, args):
        self.keywords.add('mvd')  
        self.mvd.extend(args[0])  


    def dynamic_option(self, args):
        """
        e.g. in case of 'Remark' as optional keyword in the description
        The value can be retrieved through DescriptionTransform.remark
        """
        key = str(args[0]).lower()
        attr_name = f"{key}"
        if attr_name not in self.keywords:
            setattr(self, attr_name, {})
            self.keywords.add(attr_name)
        dynamic_dict = getattr(self, attr_name)
        for value_set in args[1]:
            set_name, *values = value_set
            dynamic_dict[set_name] = values if len(values) > 1 else values[0]


    def comment(self, args):
        self.keywords.add('comment')
        self.comments = " ".join(str(child) for child in args[0].children).strip()

    def simple_value_list(self, args):
        return [str(arg) for arg in args]

    def value_list_set(self, args):
        return args

    def value_set(self, args):
        return [str(args[0])] + args[1]

    def value(self, args):
        return str(args[0])

    def set_name(self, args):
        return str(args[0])
    
    @property 
    def other_keywords(self):
        """"
        The predefined keywords are 'ViewDefinition', 'Option', 'Comment', 'ExchangeRequirement'
        Keywords in the description not from this lists are returned
        """
        return {k for k in self.keywords if k not in {'mvd', 'comment', 'exchangerequirement', 'option'}}


def parse_mvd(text):
    parsed_description = DescriptionTransform()
    try:
        parse_tree = parser.parse(text)
        parsed_description.transform(parse_tree)
    except (UnexpectedCharacters, UnexpectedEOF, UnexpectedToken) as e:
        parsed_description.mvd = []
    return parsed_description

