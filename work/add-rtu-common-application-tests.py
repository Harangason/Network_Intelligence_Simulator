import ast
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'backend/tests/test_modbus_ascii_parameter_review.py').read_text()
names=['observed_baud_requires_strict_one_percent_and_receiver_two_percent',
 'master_has_no_slave_address_and_broadcast_does_not_expect_reply',
 'quantity_and_binary_pdu_depend_selected_public_function',
 'encoded_pdu_cannot_confirm_missing_function_specific_quantity',
 'exception_function_and_user_defined_namespaces_are_not_industry_templates',
 'single_coil_literal_and_readwrite_quantities_use_own_function',
 'function_specific_fields_cannot_be_reused_by_another_public_function',
 'physical_qualification_rs485_fourwire_is_not_rs422_or_rs232']
lines=source.splitlines(keepends=True);add=[]
for node in ast.parse(source).body:
    if isinstance(node,ast.FunctionDef) and node.name in ['test_ascii_'+n for n in names]:
        start=min([node.lineno,*[d.lineno for d in node.decorator_list]])-1
        text=''.join(lines[start:node.end_lineno])
        add.append(text.replace('test_ascii_','test_rtu_shared_').replace('ma_','mr_').replace('MA.','MR.'))
assert len(add)==len(names)
target=root/'backend/tests/test_modbus_rtu_parameter_review.py'
target.write_text(target.read_text()+'\n\n# Same application/physical rules, separately exercised through the RTU profile.\n'+'\n\n'.join(add)+'\n')
