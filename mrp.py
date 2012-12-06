# -*- coding: utf-8 -*-

from datetime import datetime
from copy import copy, deepcopy

from osv import osv, fields
import decimal_precision as dp
from tools.translate import _
import netsvc
import time
import tools
import re


def rounding(f, r):
    import math
    if not r:
        return f
    return math.ceil(f / r) * r

class mrp_bom(osv.osv):
    _name = "mrp.bom"
    _inherit = "mrp.bom"
    
    _columns = {
        'template_id': fields.many2one('product.template', u'Шаблон', required=True),
        'product_id': fields.many2one('product.product', u'Продукт', required=False),
        'count_rule': fields.char(u"Правило расчета количества", size=256, required=False, help=u"Формат <r/s>(.<n>)(.param), где <r/s> - берется ли количество или параметр производимого продукта или сырья, <n> - номер строки сырья (если их несколько), param - описание параметра (если требуется не количество сырья, а его характеристика). Пример: s.1*r.length/s.1.width+0.45"),
    }
    
    _defaults = {
        'product_qty': lambda *a: 0.0,
    }
    
    def _check_template(self, cr, uid, ids, context=None):
        all_prod = []
        boms = self.browse(cr, uid, ids, context=context)
        def check_bom(boms):
            res = True
            for bom in boms:
                if bom.template_id.id in all_prod:
                    res = res and False
                all_prod.append(bom.template_id.id)
                lines = bom.bom_lines
                if lines:
                    res = res and check_bom([bom_id for bom_id in lines if bom_id not in boms])
            return res
        return check_bom(boms)
    
    def _bom_find(self, cr, uid, template_id, product_uom, properties=[]):
        """ Redefine native function - change product to template
        Finds BoM for particular template and template uom.
        @param template_id: Selected template.
        @param product_uom: Unit of measure of a template.
        @param properties: List of related properties.
        @return: False or BoM id.
        """
        
        cr.execute('select id from mrp_bom where template_id=%s and bom_id is null order by sequence', (template_id,))
        ids = map(lambda x: x[0], cr.fetchall())
        max_prop = 0
        result = False
        for bom in self.pool.get('mrp.bom').browse(cr, uid, ids):
            prop = 0
            for prop_id in bom.property_ids:
                if prop_id.id in properties:
                    prop += 1
            if (prop > max_prop) or ((max_prop == 0) and not result):
                result = bom.id
                max_prop = prop
        return result
    
    _constraints = [
        (_check_template, u'Шаблон компонента не должен быть равен шаблону производимого продукта', ['template_id']),
    ]
    
    _sql_constraints = [
        ('bom_qty_zero', 'CHECK (product_qty>=0)',  'All product quantities must be greater than 0.\n' \
            'You should install the mrp_subproduct module if you want to manage extra products on BoMs !'),
    ]
    
    def _bom_explode(self, cr, uid, bom, factor, properties=[], addthis=False, level=0, routing_id=False):
        """ Redefine native function - add product_id parameter
        Finds Products and Work Centers for related BoM for manufacturing order.
        @param bom: BoM of particular product.
        @param factor: Factor of product UoM.
        @param properties: A List of properties Ids.
        @param addthis: If BoM found then True else False.
        @param level: Depth level to find BoM lines starts from 10.
        @param product_id: ID of product, which is producing.
        @return: result: List of dictionaries containing product details.
                 result2: List of dictionaries containing Work Center details.
        """
        routing_obj = self.pool.get('mrp.routing')
        factor = factor / (bom.product_efficiency or 1.0)
        factor = rounding(factor, bom.product_rounding)
        if factor < bom.product_rounding:
            factor = bom.product_rounding
        result = []
        result2 = []
        phantom = False
        if bom.type == 'phantom' and not bom.bom_lines:
            newbom = self._bom_find(cr, uid, product.id, bom.product_uom.id, properties)
            
            if newbom:
                res = self._bom_explode(cr, uid, self.browse(cr, uid, [newbom])[0], factor*1, properties, addthis=True, level=level+10, product_id=product_id)
                result = result + res[0]
                result2 = result2 + res[1]
                phantom = True
            else:
                phantom = False
        if not phantom:
            if addthis and not bom.bom_lines:
                result.append(
                {
                    'name': bom.template_id.name,
                    'template_id': bom.template_id.id,
                    'product_qty': factor * bom.product_qty,
                    'product_uom': bom.product_uom.id,
                    'product_uos_qty': bom.product_uos and bom.product_uos_qty * factor or False,
                    'product_uos': bom.product_uos and bom.product_uos.id or False,
                })
            routing = (routing_id and routing_obj.browse(cr, uid, routing_id)) or bom.routing_id or False
            if routing:
                for wc_use in routing.workcenter_lines:
                    wc = wc_use.workcenter_id
                    d, m = divmod(factor, wc_use.workcenter_id.capacity_per_cycle)
                    mult = (d + (m and 1.0 or 0.0))
                    cycle = mult * wc_use.cycle_nbr
                    result2.append({
                        'name': tools.ustr(wc_use.name) + ' - '  + tools.ustr(bom.template_id.name),
                        'workcenter_id': wc.id,
                        'sequence': level+(wc_use.sequence or 0),
                        'cycle': cycle,
                        'hour': float(wc_use.hour_nbr*mult + ((wc.time_start or 0.0)+(wc.time_stop or 0.0)+cycle*(wc.time_cycle or 0.0)) * (wc.time_efficiency or 1.0)),
                    })
            for bom2 in bom.bom_lines:
                res = self._bom_explode(cr, uid, bom2, factor, properties, addthis=True, level=level+10)
                result = result + res[0]
                result2 = result2 + res[1]
        return result, result2
    
    def onchange_template_id(self, cr, uid, ids, template_id, name, context=None):
        """ Changes UoM if template_id changes.
        @param template_id: Changed template_id
        @param name: choosen name
        @return:  Dictionary of changed values
        """
        if template_id:
            tpl = self.pool.get('product.template').browse(cr, uid, template_id, context=context)
            value = {'product_uom': tpl.uom_id.id, 'name': tpl.name}
            return {'value': value}
        return {}
    
mrp_bom()

class mrp_production(osv.osv):
    _inherit = 'mrp.production'
    _name = 'mrp.production'
    
    def calc_product_count(self, cr, uid, ids, context=None):
        if isinstance(ids, list):
            ids = ids[0]
        p = self.browse(cr, uid, ids, context=context)
        if p.state != 'draft':
            raise osv.except_osv(u'Предупреждение', u'Вы не можете пересчитать количество утвержденного заказа')
        if not len(p.product_lines):
            raise osv.except_osv(u'Предупреждение', u'Не выбрано сырье. Перейдите на вкладку "Плановые продукты", и нажмите кнопку "Подсчитать данные".')
        for line in p.product_lines:
            if not line.product_id:
                raise osv.except_osv(u'Предупреждение', u'Сначала заполните все характеристики сырья.')
        if not p.product_id.id:
            raise osv.except_osv(u'Предупреждение', u'Сначала задайте характеристики производимого продукта.')
        if not p.bom_id.id:
            raise osv.except_osv(u'Предупреждение', u'Для этого шаблона нет спецификации.')
        elif p.bom_id.product_qty or not p.bom_id.count_rule:
            ret = p.bom_id.product_qty
        else:
            rule = p.bom_id.count_rule
            orig_rule = copy(rule)
            
            for param in p.product_id.dimension_value_ids:
                rule = rule.replace('r.'+param.dimension_id.description, param.option_id.name)
            
            for i, line in reversed(list(enumerate(p.product_lines))):
                for param in line.product_id.dimension_value_ids:
                    rule = rule.replace('s.'+str(i+1)+'.'+param.dimension_id.description, param.option_id.name)
                rule = rule.replace('s.'+str(i+1), str(line.product_qty))                       
            rule = rule.replace(',', '.')
            try:
                ret = round(eval(rule), 3)
                #print 'Eval success: %s - %s' % (rule, str(ret))
            except Exception, e:
                print 'Wrong parsing "%s" from "%s"' % (rule, orig_rule)
                print 'Production calculating count: eval error - %s' % e.message
                raise osv.except_osv(u'Предупреждение', u'Неверная формула расчета')
            if ret % 1 > 0.95:
                ret = ret - (ret % 1) + 1
            else:
                ret = ret - (ret % 1)
        self.write(cr, uid, ids, {'product_qty': ret})
        return ret
               
    
    _columns = {
        'tmpl_id': fields.dummy(string='Template', relation='product.template', type='many2one'),
        'template_id': fields.many2one('product.template', u'Шаблон', required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'product_id': fields.many2one('product.product', u'Продукт', required=False, readonly=True, states={'draft':[('readonly',False)]}),
        #'multi': fields.dummy(string='Multi fields'),
        'params': fields.dummy(string='Params fields'),
    }
    
    _defaults = {
        'product_qty': 0, 
    }
    
    def _check_qty(self, cr, uid, ids, context=None):
#        for order in self.browse(cr, uid, ids, context=context):
#            if order.product_qty <= 0:
#                return False
        return True
    
    _constraints = [
        (_check_qty, u'Количество производимой продукции должно быть больше нуля', ['product_qty']),
    ]

    def fields_view_get(self, cr, uid, view_id, view_type='form', context=None, toolbar=False, submenu=False):
        fields = super(mrp_production, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        
#        if view_type == 'form' and 'tmpl_id' in fields['fields']:
#            tmpl_ids = self.pool.get('product.template').search(cr, uid, [], context=context)
#            templates = self.pool.get('product.template').browse(cr, uid, tmpl_ids, context=context)
#            
#            fields['fields']['tmpl_id']['selection'] = []
#            
#            for rec in templates:
#                fields['fields']['tmpl_id']['selection'].append((rec.id, rec.name))
            
        if view_type == 'tree':
            # Add columns with product's parameters
            type_obj = self.pool.get('product.variant.dimension.type')
            types = type_obj.search(cr, uid, [('show_in_tree', '=', True)])
            types = type_obj.browse(cr, uid, types)
            arch = ''
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
        else:
            #fields['arch']=re.sub('<field\s+name=(\'|\")multi(\'|\")[^>]+>', '', fields['arch'])
            fields['arch']=re.sub('<field\s+name=(\'|\")params(\'|\")[^>]+>', '', fields['arch'].decode('utf-8'))
        
        return fields
    
    def read(self, cr, uid, ids, fields=None, context=None, load="_classic_read"):
        time1 = time.time()
        ret = super(mrp_production, self).read(cr, uid, ids, fields=fields, context=context, load=load)
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
        ret = super(mrp_production, self).read_group(cr, uid, domain, fields, group_by_fields, p1, p2, context, sort)
        return ret
       
    def get_default_values(self, cr, uid, form_values, related_field, view_name=None):
        """
        Hook-function to get default values for move_lines
        @param <obj>: psycopg2 cursor
        @param <int>: user ID
        @param <dict>: values from form to calculate
        @param <str>: field name, which was related to current web-widget
        """
        try:
            product_id = form_values['product_id']
            count_products = form_values['count_products']
            
            if related_field == 'move_lines':
                location_src_id = form_values['location_src_id']
                location_dest_id = 7 # Производство (Production)
            elif related_field == 'move_created_ids':
                location_src_id = 7 # Производство (Production)
                location_dest_id = form_values['location_dest_id']
            else:
                location_src_id = form_values['location_src_id']
                location_dest_id = form_values['location_dest_id']
        except KeyError, e:
            raise osv.except_osv('Not enough data for calculate values')
        product = self.pool.get('product.product').browse(cr, uid, product_id)
        product_uom = product.uom_id.id    
        ret = {'product_uom': product_uom, 
                'product_qty': count_products, 
                'location_id': location_src_id,
                'location_dest_id': location_dest_id,
                'name': product.product_name,
                'date': time.strftime('%Y-%m-%d %H:%M:%S'),
                'date_expected': time.strftime('%Y-%m-%d %H:%M:%S'),
                }
        params = {}
        for param in product.dimension_value_ids:
            params[param.dimension_id.description] = param.option_id.name
        ret.update(params)
        
        return ret
        
        
    def template_id_change(self, cr, uid, ids, template_id, context=None):
        """ Finds UoM and Bom of changed template.
        @param template_id: Id of changed template.
        @return: Dictionary of values and domain.
        """
        if not template_id:
            return {'value': {
                'product_uom': False,
                'bom_id': False,
                'routing_id': False,
                'product_id': False,
            }}
        self.write(cr, uid, ids, {'product_id': False})    
        
        bom_obj = self.pool.get('mrp.bom')
        template = self.pool.get('product.template').browse(cr, uid, template_id, context=context)
        bom_id = bom_obj._bom_find(cr, uid, template.id, template.uom_id and template.uom_id.id, [])
        routing_id = False
        if bom_id:
            bom_point = bom_obj.browse(cr, uid, bom_id, context=context)
            routing_id = bom_point.routing_id.id or False
        value = {
            'product_uom': template.uom_id and template.uom_id.id or False,
            'bom_id': bom_id,
            'routing_id': routing_id,
            'product_id': False,
        }
        domain = {}
        domain['bom_id'] = [('template_id', '=', template.id), ('bom_id', '=', False)]
        
        return {'value': value, 'domain': domain}
        
            
    def action_compute(self, cr, uid, ids, properties=[], context=None):
        """ Redefine native function
        Computes bills of material of a product.
        @param properties: List containing dictionaries of properties.
        @return: No. of products.
        """
        results = []
        bom_obj = self.pool.get('mrp.bom')
        uom_obj = self.pool.get('product.uom')
        prod_line_obj = self.pool.get('mrp.production.product.line')
        workcenter_line_obj = self.pool.get('mrp.production.workcenter.line')
        for production in self.browse(cr, uid, ids):
            cr.execute('delete from mrp_production_product_line where production_id=%s', (production.id,))
            cr.execute('delete from mrp_production_workcenter_line where production_id=%s', (production.id,))
            bom_point = production.bom_id
            bom_id = production.bom_id.id
            if not bom_point:
                bom_id = bom_obj._bom_find(cr, uid, production.template_id.id, production.product_uom.id, properties)
                if bom_id:
                    bom_point = bom_obj.browse(cr, uid, bom_id)
                    routing_id = bom_point.routing_id.id or False
                    self.write(cr, uid, [production.id], {'bom_id': bom_id, 'routing_id': routing_id})

            if not bom_id:
                raise osv.except_osv(_('Error'), _("Couldn't find a bill of material for this product."))
            if bom_point.product_qty and production.product_qty and not bom_point.count_rule:
                prod_qty = production.product_qty
            else:
                prod_qty = 1
            factor = uom_obj._compute_qty(cr, uid, production.product_uom.id, prod_qty, bom_point.product_uom.id)
            res = bom_obj._bom_explode(cr, uid, bom_point, factor / (bom_point.product_qty or 1), properties, routing_id=production.routing_id.id)
            results = res[0]
            for line in results:
                line['production_id'] = production.id
                prod_line_obj.create(cr, uid, line)
                
        return len(results)
    
    def action_confirm(self, cr, uid, ids, context=None):
        """ Redefine native function
        Confirms production order.
        @return: Newly generated Shipment Id.
        """
        
        ps = self.browse(cr, uid, ids, context=context)
        for p in ps:
            if not p.product_id:
                raise osv.except_osv('Предупреждение', 'Сначала необходимо задать характеристики производимого продукта.')
            if p.product_qty <= 0:
                product_qty = self.calc_product_count(cr, uid, p.id, context=context)
                if not product_qty or product_qty < 0:
                    raise osv.except_osv('Предупреждение', 'Сначала рассчитайте количество производимого продукта.')
                else:
                    self.write(cr, uid, p.id, {'product_qty': product_qty})
            
            for item in p.product_lines:
                if not item.product_id:
                    raise osv.except_osv('Предупреждение', 'Необходимо вручную задать плановые продукты. Перейдите на закладку "Плановые продукты", нажмите "Подсчитать данные" и задайте продукт для каждого шаблона.')
        
        shipment_id = False
        wf_service = netsvc.LocalService("workflow")
        uncompute_ids = filter(lambda x:x, [not x.product_lines and x.id or False for x in self.browse(cr, uid, ids, context=context)])
        self.action_compute(cr, uid, uncompute_ids, context=context)
        for production in self.browse(cr, uid, ids, context=context):
            
            factor = self.pool.get('product.uom')._compute_qty_simple(cr, uid, production.product_uom.id, production.product_qty, production.bom_id.product_uom.id)
            res = self.pool.get('mrp.bom')._bom_explode(cr, uid, production.bom_id, factor / 1, [], routing_id=production.routing_id.id)
            results2 = res[1]
            for line in results2:
                line['production_id'] = production.id
                self.pool.get('mrp.production.workcenter.line').create(cr, uid, line)
            
            
            shipment_id = self._make_production_internal_shipment(cr, uid, production, context=context)
            produce_move_id = self._make_production_produce_line(cr, uid, production, context=context)
            
            # Take routing location as a Source Location.
            source_location_id = production.location_src_id.id
            if production.bom_id.routing_id and production.bom_id.routing_id.location_id:
                source_location_id = production.bom_id.routing_id.location_id.id

            for line in production.product_lines:
                consume_move_id = self._make_production_consume_line(cr, uid, line, produce_move_id, source_location_id=source_location_id, context=context)
                shipment_move_id = self._make_production_internal_shipment_line(cr, uid, line, shipment_id, consume_move_id,\
                                 destination_location_id=source_location_id, context=context)
                self._make_production_line_procurement(cr, uid, line, shipment_move_id, context=context)
                    
            wf_service.trg_validate(uid, 'stock.picking', shipment_id, 'button_confirm', cr)
            production.write({'state':'confirmed'}, context=context)
            message = _("Manufacturing order '%s' is scheduled for the %s.") % (
                production.name,
                datetime.strptime(production.date_planned,'%Y-%m-%d %H:%M:%S').strftime('%m/%d/%Y'),
            )
            self.log(cr, uid, production.id, message)
        return shipment_id

    def action_produce(self, cr, uid, production_id, products, production_mode, context=None):
        """ Redefine native function
        To produce final product based on production mode (consume/consume&produce).
        If Production mode is consume, all stock move lines of raw materials will be done/consumed.
        If Production mode is consume & produce, all stock move lines of raw materials will be done/consumed
        and stock move lines of final product will be also done/produced.
        @param production_id: the ID of mrp.production object
        @param products : products to produce with their counts or just count. 
            <dict> - if there are a few products. In this case use sum of count all products
            <float> - if there is one product - just count
        @param production_mode: specify production mode (consume/consume&produce).
        @return: True
        """
        stock_mov_obj = self.pool.get('stock.move')
        production = self.browse(cr, uid, production_id, context=context)

        produced_qty = 0
        for produced_product in production.move_created_ids2:
            if (produced_product.scrapped) or (produced_product.product_id.id <> production.product_id.id):
                continue
            if production.product_id.id == produced_product.product_id.id:
                produced_qty += produced_product.product_qty
        # Calc count of main products to produce
        production_qty = 0.00
        
        if isinstance(products, dict):
            for key, val in products.items():
                if production.product_id.id == key:
                    production_qty += val
        else:
            production_qty = products

        if production_mode in ['consume','consume_produce']:
            consumed_data = {}

            # Calculate already consumed qtys
            for consumed in production.move_lines2:
                if consumed.scrapped:
                    continue
                if not consumed_data.get(consumed.product_id.id, False):
                    consumed_data[consumed.product_id.id] = 0
                consumed_data[consumed.product_id.id] += consumed.product_qty

            # Find product qty to be consumed and consume it
            for scheduled in production.product_lines:

                # total qty of consumed product we need after this consumption
                total_consume = ((production_qty + produced_qty) * scheduled.product_qty / production.product_qty)

                # qty available for consume and produce
                qty_avail = scheduled.product_qty - consumed_data.get(scheduled.product_id.id, 0.0)

                if qty_avail <= 0.0:
                    # there will be nothing to consume for this raw material
                    continue

                raw_product = [move for move in production.move_lines if move.product_id.id==scheduled.product_id.id]
                if raw_product:
                    # qtys we have to consume
                    qty = total_consume - consumed_data.get(scheduled.product_id.id, 0.0)

                    if qty > qty_avail:
                        # if qtys we have to consume is more than qtys available to consume
                        prod_name = scheduled.product_id.name_get()[0][1]
                        raise osv.except_osv(_('Warning!'), _('You are going to consume total %s quantities of "%s".\nBut you can only consume up to total %s quantities.') % (qty, prod_name, qty_avail))
                    if qty <= 0.0:
                        # we already have more qtys consumed than we need 
                        continue

                    raw_product[0].action_consume(qty, raw_product[0].location_id.id, context=context)

        if production_mode == 'consume_produce':
            # To produce remaining qty of final product
            #vals = {'state':'confirmed'}
            #final_product_todo = [x.id for x in production.move_created_ids]
            #stock_mov_obj.write(cr, uid, final_product_todo, vals)
            #stock_mov_obj.action_confirm(cr, uid, final_product_todo, context)
            produced_products = {}
            for produced_product in production.move_created_ids2:
                if produced_product.scrapped:
                    continue
                if not produced_products.get(produced_product.product_id.id, False):
                    produced_products[produced_product.product_id.id] = 0
                produced_products[produced_product.product_id.id] += produced_product.product_qty

            for produce_product in production.move_created_ids:
                produced_qty = produced_products.get(produce_product.product_id.id, 0)
                subproduct_factor = self._get_subproduct_factor(cr, uid, production.id, produce_product.id, context=context)
                #rest_qty = (subproduct_factor * production.product_qty) - produced_qty

                if isinstance(products, dict):
                    count_product = products.get(produce_product.product_id.id, False)
                else:
                    count_product = products
                if count_product > produce_product.product_qty:#rest_qty < production_qty:
                    prod_name = produce_product.product_id.name_get()[0][1]
                    raise osv.except_osv(_('Warning!'), _('You are going to produce total %s quantities of "%s".\nBut you can only produce up to total %s quantities.') % (production_qty, prod_name, produce_product.product_qty))
                                
                if count_product and produce_product.product_qty > 0: #and rest_qty > 0:
                    stock_mov_obj.action_consume(cr, uid, [produce_product.id], (subproduct_factor * count_product), context=context)

        for raw_product in production.move_lines2:
            new_parent_ids = []
            parent_move_ids = [x.id for x in raw_product.move_history_ids]
            for final_product in production.move_created_ids2:
                if final_product.id not in parent_move_ids:
                    new_parent_ids.append(final_product.id)
            for new_parent_id in new_parent_ids:
                stock_mov_obj.write(cr, uid, [raw_product.id], {'move_history_ids': [(4,new_parent_id)]})

        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, 'mrp.production', production_id, 'button_produce_done', cr)
        return True
        

mrp_production()

class mrp_production_product_line(osv.osv):
    _name = 'mrp.production.product.line'
    _inherit = 'mrp.production.product.line'
    
    _columns = {
        'template_id': fields.many2one('product.template', u'Шаблон', required=True),
        'product_id': fields.many2one('product.product', u'Продукт', required=False),
        'params': fields.dummy(string='Params fields'),
    }
    
    def fields_view_get(self, cr, uid, view_id, view_type='form', context=None, toolbar=False, submenu=False):
        fields = super(mrp_production_product_line, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)            
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

        #fields['arch']=re.sub('<field\s+name=(\'|\")multi(\'|\")[^>]+>', '    ', fields['arch'])
        fields['arch']=re.sub('<field\s+name=(\'|\")params(\'|\")[^>]+>', arch, fields['arch'].decode('utf-8'))
        
        return fields
    
    def read(self, cr, uid, ids, fields=None, context=None, load="_classic_read"):
        time1 = time.time()
        ret = super(mrp_production_product_line, self).read(cr, uid, ids, fields=fields, context=context, load=load)
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
        ret = super(mrp_production_product_line, self).read_group(cr, uid, domain, fields, group_by_fields, p1, p2, context, sort)
        return ret
    
    def create(self, cr, uid, vals, context=None):
        if 'template_id' not in vals and 'product_id' in vals and vals['product_id']:
            vals['template_id'] = self.pool.get('product.product').browse(cr, uid, vals['product_id']).product_tmpl_id.id
        ret = super(mrp_production_product_line, self).create(cr, uid, vals, context=context)
        return ret
    
    def write(self, cr, uid, ids, vals, context=None):
        if 'template_id' not in vals and 'product_id' in vals and vals['product_id']:
            vals['template_id'] = self.pool.get('product.product').browse(cr, uid, vals['product_id']).product_tmpl_id.id
        ret = super(mrp_production_product_line, self).write(cr, uid, ids, vals, context=context)
        return ret
    
        
    def onchange_product_id(self, cr, uid, ids, product_id, template_id, context=None):
        value = {}
        domain = {}
        if template_id:
            tmpl = self.pool.get('product.template').browse(cr, uid, template_id)
            if tmpl:
                domain.update({'product_id': [('product_tmpl_id', '=', template_id)]})
                value.update({'product_uom': tmpl.uom_id.id,
                              'name': tmpl.name,
                              })
        
        if product_id:
            product = self.pool.get('product.product').browse(cr, uid, product_id)
            if product:
                template_id = product.product_tmpl_id.id
                uom = product.uom_id.id
                value.update({'template_id': template_id, 
                              'product_uom': uom,
                              'name': product.name,
                              })
            
        return {'value': value, 'domain': domain}
    
mrp_production_product_line()

class product_uom(osv.osv):
    _name = "product.uom"
    _inherit = "product.uom"
    
    def _compute_qty_simple(self, cr, uid, from_uom_id, qty, to_uom_id=False):
        if not from_uom_id or not qty or not to_uom_id:
            return qty
        uoms = self.browse(cr, uid, [from_uom_id, to_uom_id])
        if uoms[0].id == from_uom_id:
            from_unit, to_unit = uoms[0], uoms[-1]
        else:
            from_unit, to_unit = uoms[-1], uoms[0]

        if from_unit.category_id.id <> to_unit.category_id.id:
            raise osv.except_osv(_('Error !'), _('Conversion from Product UoM %s to Default UoM %s is not possible as they both belong to different Category!.') % (from_unit.name,to_unit.name,))
            
        amount = qty / from_unit.factor
        if to_unit:
            amount = amount * to_unit.factor
        return amount
    
product_uom()
