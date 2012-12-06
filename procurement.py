# -*- encoding: utf-8 -*-

from osv import fields, osv
from copy import copy
import decimal_precision as dp
import netsvc
import re
import time
from tools.safe_eval import safe_eval
from tools.translate import _

LOGGER = netsvc.Logger()

class procurement_order(osv.osv):
    _name = "procurement.order"
    _inherit = "procurement.order"
    
    _columns = {
        'params': fields.dummy(string='Params fields'),
    }
    
    def fields_view_get(self, cr, uid, view_id, view_type='form', context=None, toolbar=False, submenu=False):
        fields = super(procurement_order, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        arch = ''
        if view_type == 'tree':
            # Add columns with product's parameters
            type_obj = self.pool.get('product.variant.dimension.type')
            types = type_obj.search(cr, uid, [('show_in_tree', '=', True)])
            types = type_obj.browse(cr, uid, types)
            for type in types:
                fields['fields'].update({type.description: {
                                                     'select': True,
                                                     'selectable': True,
                                                     'size': 64,
                                                     'string': type.name,
                                                     'type': 'char',
                                                     }})
                arch += '<field name="%s" />' % type.description
            
        fields['arch']=re.sub('<field\s+name=(\'|\")params(\'|\")[^>]+>', arch, fields['arch'].decode('utf-8'))
       
        return fields
    
    def read(self, cr, uid, ids, fields=None, context=None, load="_classic_read"):
        time1 = time.time()
        ret = super(procurement_order, self).read(cr, uid, ids, fields=fields, context=context, load=load)
        type_obj = self.pool.get('product.variant.dimension.type')
        types = type_obj.search(cr, uid, [('show_in_tree', '=', True)])

        param_fields = []
        if fields and 'product_id' in fields:
            for type in type_obj.browse(cr, uid, types):
                if type.description in fields:
                    param_fields.append(type.description)
        
            product_ids = [item['product_id'] for item in ret]
            product_ids = [i[0] if isinstance(i, tuple) else i for i in product_ids]
            ff = []
            for i, item in enumerate(product_ids):
                if not item:
                    ff.append(i)
            ff.reverse()
            for i in ff:
                del(product_ids[i])
                        
            if param_fields:
                for product in self.pool.get('product.product').browse(cr, uid, product_ids):
                    ind = False
                    for i, item in enumerate(product_ids):
                        if item == product.id:
                            ind = i
                            break
                    
                    for param_value in product.dimension_value_ids:
                        if param_value.dimension_id.show_in_tree and param_value.dimension_id.description in param_fields:   
                            ret[ind].update({param_value.dimension_id.description: param_value.option_id.name})
        
        time2 = time.time()
        if (time2-time1) > 1:
            print "Time for showing parameters - %s" % round(time2-time1)
        return ret
    
    def read_group(self, cr, uid, domain, fields=None, group_by_fields=None, p1=False, p2=False, context=None, sort=False):
        dims = self.pool.get('product.variant.dimension.type').search(cr, uid, [])
        for dim in self.pool.get('product.variant.dimension.type').browse(cr, uid, dims):
            if dim.description in fields:
                del(fields[fields.index(dim.description)])
        ret = super(procurement_order, self).read_group(cr, uid, domain, fields, group_by_fields, p1, p2, context, sort)
        return ret    
    
procurement_order()
        