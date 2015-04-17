from amslib.core.manager import BaseManager



class ArgumentCompletion(BaseManager):

    # leaving this here in a comment to ease debugging until i get a chance to build a proper debug mode
    # TODO build proper debug mode
    # import pprint
    # with open('/tmp/ams_completion_debug.log','wb') as fh:
    #     fh.write(pprint.pformat(kwargs))


    def _general_db_completion(self, table, column, need_distinct=True, filters={}):
        rval = []
        distinct = ''
        if need_distinct:
            distinct = 'distinct'
        sql = "select {0} {1} from {2} ".format(distinct, column, table)
        vals = []
        wheres = []
        if filters:
            for k,v in filters.iteritems():
                wheres.append("{0}=%s".format(k))
                vals.append(v)

        if wheres:
            sql += " where "
            sql += " and ".join(wheres)
        self.db.execute(sql, vals)
        rows = self.db.fetchall()
        if rows:
            for row in rows:
                if row[0]:
                    rval.append(row[0])
        return rval



    def security_group_id(self, **kwargs):
        filters = {}
        if 'parsed_args' in kwargs and 'vpc_id' in kwargs['parsed_args'] and kwargs['parsed_args'].vpc_id:
            filters['vpc_id'] = kwargs['parsed_args'].vpc_id
        if 'parsed_args' in kwargs and 'region' in kwargs['parsed_args'] and kwargs['parsed_args'].region:
            filters['region'] = kwargs['parsed_args'].region
        elif 'parsed_args' in kwargs and 'zone' in kwargs['parsed_args'] and kwargs['parsed_args'].zone:
            r = self.__region_from_az(kwargs['parsed_args'].zone)
            if r:
                filters['region'] = r
        return self._general_db_completion('security_groups', 'security_group_id', False, filters)


    def security_group_vpc(self, **kwargs):
        filters = {}
        if 'parsed_args' in kwargs and 'vpc_id' in kwargs['parsed_args'] and kwargs['parsed_args'].vpc_id:
            filters['vpc_id'] = kwargs['parsed_args'].vpc_id
        if 'parsed_args' in kwargs and 'region' in kwargs['parsed_args'] and kwargs['parsed_args'].region:
            filters['region'] = kwargs['parsed_args'].region
        elif 'parsed_args' in kwargs and 'zone' in kwargs['parsed_args'] and kwargs['parsed_args'].zone:
            r = self.__region_from_az(kwargs['parsed_args'].zone)
            if r:
                filters['region'] = r
        return self._general_db_completion('security_groups', 'vpc_id', True, filters)


    def security_group_name(self, **kwargs):
        filters = {}
        if 'parsed_args' in kwargs and 'vpc_id' in kwargs['parsed_args'] and kwargs['parsed_args'].vpc_id:
            filters['vpc_id'] = kwargs['parsed_args'].vpc_id
        if 'parsed_args' in kwargs and 'region' in kwargs['parsed_args'] and kwargs['parsed_args'].region:
            filters['region'] = kwargs['parsed_args'].region
        elif 'parsed_args' in kwargs and 'zone' in kwargs['parsed_args'] and kwargs['parsed_args'].zone:
            r = self.__region_from_az(kwargs['parsed_args'].zone)
            if r:
                filters['region'] = r
        return self._general_db_completion('security_groups', 'name', False)


    def region(self, **kwargs):
        return self._general_db_completion('availability_zones', 'region', True)

    def availability_zone(self, **kwargs):
        filters = {}
        if 'parsed_args' in kwargs and 'region' in kwargs['parsed_args'] and kwargs['parsed_args'].region:
            filters['region'] = kwargs['parsed_args'].region
        return self._general_db_completion('availability_zones', 'availability_zone', False, filters)

    def instance_id(self, **kwargs):
        return self._general_db_completion('hosts', 'instance_id', False)

    def ami_id(self, **kwargs):
        filters = {}
        if 'parsed_args' in kwargs and 'region' in kwargs['parsed_args'] and kwargs['parsed_args'].region:
            filters['region'] = kwargs['parsed_args'].region
        elif 'parsed_args' in kwargs and 'zone' in kwargs['parsed_args'] and kwargs['parsed_args'].zone:
            r = self.__region_from_az(kwargs['parsed_args'].zone)
            if r:
                filters['region'] = r
        return self._general_db_completion('amis', 'ami_id', False, filters)

    def vpc_id(self, **kwargs):
        filters = {}
        if 'parsed_args' in kwargs and 'region' in kwargs['parsed_args'] and kwargs['parsed_args'].region:
            filters['region'] = kwargs['parsed_args'].region
        elif 'parsed_args' in kwargs and 'zone' in kwargs['parsed_args'] and kwargs['parsed_args'].zone:
            r = self.__region_from_az(kwargs['parsed_args'].zone)
            if r:
                filters['region'] = r
        return self._general_db_completion('vpcs', 'vpc_id', False, filters)

    def subnet_id(self, **kwargs):
        filters = {}
        if 'parsed_args' in kwargs and 'vpc_id' in kwargs['parsed_args'] and kwargs['parsed_args'].vpc_id:
            filters['vpc_id'] = kwargs['parsed_args'].vpc_id
        if 'parsed_args' in kwargs and 'zone' in kwargs['parsed_args'] and kwargs['parsed_args'].zone:
            filters['availability_zone'] = kwargs['parsed_args'].zone
        return self._general_db_completion('subnets', 'subnet_id', False, filters)

    def keypair(self, **kwargs):
        filters = {}
        if 'parsed_args' in kwargs and 'region' in kwargs['parsed_args'] and kwargs['parsed_args'].region:
            filters['region'] = kwargs['parsed_args'].region
        elif 'parsed_args' in kwargs and 'zone' in kwargs['parsed_args'] and kwargs['parsed_args'].zone:
            r = self.__region_from_az(kwargs['parsed_args'].zone)
            if r:
                filters['region'] = r
        return self._general_db_completion('key_pairs', 'key_name', False, filters)

    def __region_from_az(self, az):
        self.db.execute("select region from availability_zones where availability_zone = %s", (az,))
        row = self.db.fetchone()
        if not row:
            return None
        return row[0]

    def config_value(self, **kwargs):
        if 'parsed_args' in kwargs and 'name' in kwargs['parsed_args'] and kwargs['parsed_args'].name:
            self.db.execute("select `type`,`value` from config where `var`=%s and configurable=1",(kwargs['parsed_args'].name, ))
            row = self.db.fetchone()
            if row:
                if row[0] == 'bool':
                    return ['0', '1']
                else:
                    return [row[1]]
        return None

    def config_name(self, **kwargs):
        filters = {'configurable': 1}
        return self._general_db_completion('config', '`var`', False, filters)


    def host_template_id(self, **kwargs):
        filters = {}
        if 'parsed_args' in kwargs and 'region' in kwargs['parsed_args'] and kwargs['parsed_args'].region:
            filters['region'] = kwargs['parsed_args'].region
        elif 'parsed_args' in kwargs and 'zone' in kwargs['parsed_args'] and kwargs['parsed_args'].zone:
            r = self.__region_from_az(kwargs['parsed_args'].zone)
            if r:
                filters['region'] = r
        return self._general_db_completion('host_templates', 'template_id', False, filters)

    def host_template_name(self, **kwargs):
        filters = {}
        if 'parsed_args' in kwargs and 'region' in kwargs['parsed_args'] and kwargs['parsed_args'].region:
            filters['region'] = kwargs['parsed_args'].region
        elif 'parsed_args' in kwargs and 'zone' in kwargs['parsed_args'] and kwargs['parsed_args'].zone:
            r = self.__region_from_az(kwargs['parsed_args'].zone)
            if r:
                filters['region'] = r
        return self._general_db_completion('host_templates', 'template_name', False, filters)


    def template_tag(self, **kwargs):
        filters = {}
        if 'parsed_args' in kwargs and 'template_id' in kwargs['parsed_args'] and kwargs['parsed_args'].template_id:
            filters['template_id'] = kwargs['parsed_args'].template_id
        if 'parsed_args' in kwargs and 'template_name' in kwargs['parsed_args'] and kwargs['parsed_args'].template_name:
            filters['template_name'] = kwargs['parsed_args'].template_name
        return self._general_db_completion('host_templates_tags', 'name', True, filters)

    def template_security_group(self, **kwargs):
        filters = {}
        if 'parsed_args' in kwargs and 'template_id' in kwargs['parsed_args'] and kwargs['parsed_args'].template_id:
            filters['template_id'] = kwargs['parsed_args'].template_id
        if 'parsed_args' in kwargs and 'template_name' in kwargs['parsed_args'] and kwargs['parsed_args'].template_name:
            filters['template_name'] = kwargs['parsed_args'].template_name
        return self._general_db_completion('host_templates_sg_associations', 'security_group_id', True, filters)


class HostTemplateArgumentCompletion(ArgumentCompletion):

    def map_template_values_to_parsed_args(self, **kwargs):
        template_row = None
        if 'parsed_args' in kwargs and 'template_id' in kwargs['parsed_args'] and kwargs['parsed_args'].template_id:
            self.db.execute("select region, instance_type, ami_id, key_name, zone, monitoring, vpc_id, subnet_id, private_ip, ebs_optimized, name from host_templates where template_id=%s", (kwargs['parsed_args'].template_id, ))
            template_row = self.db.fetchone()
        elif 'parsed_args' in kwargs and 'template_name' in kwargs['parsed_args'] and kwargs['parsed_args'].template_name:
            self.db.execute("select region, instance_type, ami_id, key_name, zone, monitoring, vpc_id, subnet_id, private_ip, ebs_optimized, name from host_templates where template_name=%s", (kwargs['parsed_args'].template_name, ))
            template_row = self.db.fetchone()

        if template_row:
            cols = ['region', 'instance_type', 'ami_id', 'key_name', 'zone', 'monitoring', 'vpc_id', 'subnet_id', 'private_ip', 'ebs_optimized', 'name']
            col_id = 0
            for col in cols:
                if template_row[col_id] is not None:
                    if getattr(kwargs['parsed_args'], col) is None:
                        setattr(kwargs['parsed_args'], col, template_row[col_id])
                col_id += 1


    def region(self, **kwargs):
        self.map_template_values_to_parsed_args(**kwargs)
        return ArgumentCompletion.region(self, **kwargs)

    def ami_id(self, **kwargs):
        self.map_template_values_to_parsed_args(**kwargs)
        return ArgumentCompletion.ami_id(self, **kwargs)

    def keypair(self, **kwargs):
        self.map_template_values_to_parsed_args(**kwargs)
        return ArgumentCompletion.keypair(self, **kwargs)

    def availability_zone(self, **kwargs):
        self.map_template_values_to_parsed_args(**kwargs)
        return ArgumentCompletion.availability_zone(self, **kwargs)

    def vpc_id(self, **kwargs):
        self.map_template_values_to_parsed_args(**kwargs)
        return ArgumentCompletion.vpc_id(self, **kwargs)

    def subnet_id(self, **kwargs):
        self.map_template_values_to_parsed_args(**kwargs)
        return ArgumentCompletion.subnet_id(self, **kwargs)

    def security_group_id(self, **kwargs):
        self.map_template_values_to_parsed_args(**kwargs)
        return ArgumentCompletion.security_group_id(self, **kwargs)



