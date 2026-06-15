# ── Virtual Network (optional) ────────────────────────────────────
# Only created when var.use_vnet is true.
# Enabling VNet integration for an existing ACE forces recreation.

resource "azurerm_virtual_network" "cmpd" {
  count = var.use_vnet ? 1 : 0

  name                = "${var.prefix}-${var.environment}-vnet"
  location            = azurerm_resource_group.cmpd.location
  resource_group_name = azurerm_resource_group.cmpd.name
  address_space       = [var.vnet_address_space]

  tags = local.tags
}

resource "azurerm_subnet" "ace" {
  count = var.use_vnet ? 1 : 0

  name                 = "${var.prefix}-${var.environment}-ace-subnet"
  resource_group_name  = azurerm_resource_group.cmpd.name
  virtual_network_name = azurerm_virtual_network.cmpd[0].name
  address_prefixes     = [var.ace_subnet_prefix]

  delegation {
    name = "aca-delegation"
    service_delegation {
      name    = "Microsoft.App/environments"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

resource "azurerm_network_security_group" "ace" {
  count = var.use_vnet ? 1 : 0

  name                = "${var.prefix}-${var.environment}-ace-nsg"
  location            = azurerm_resource_group.cmpd.location
  resource_group_name = azurerm_resource_group.cmpd.name

  security_rule {
    name                       = "AllowHttpInbound"
    priority                   = 1000
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "80"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "AllowHttpsInbound"
    priority                   = 1001
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "AllowAzureLoadBalancer"
    priority                   = 1002
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "AzureLoadBalancer"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "DenyAllOtherInbound"
    priority                   = 4000
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  tags = local.tags
}

resource "azurerm_subnet_network_security_group_association" "ace" {
  count = var.use_vnet ? 1 : 0

  subnet_id                 = azurerm_subnet.ace[0].id
  network_security_group_id = azurerm_network_security_group.ace[0].id
}

# ── DNS zone (optional) ───────────────────────────────────────────
# Only created when var.dns_domain is set.

resource "azurerm_dns_zone" "cmpd" {
  count = var.dns_domain != "" ? 1 : 0

  name                = var.dns_domain
  resource_group_name = azurerm_resource_group.cmpd.name

  tags = local.tags
}

resource "azurerm_dns_cname_record" "backend" {
  count = var.dns_domain != "" ? 1 : 0

  name                = var.prefix
  zone_name           = azurerm_dns_zone.cmpd[0].name
  resource_group_name = azurerm_resource_group.cmpd.name
  ttl                 = 300
  record              = azurerm_container_app.backend.latest_revision_fqdn
}
