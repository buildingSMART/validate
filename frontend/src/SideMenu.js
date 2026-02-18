import * as React from 'react';
import Box from '@mui/material/Box';
import Drawer from '@mui/material/Drawer';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import HomeIcon from '@mui/icons-material/Home';
import InfoIcon from '@mui/icons-material/Info';
import CheckIcon from '@mui/icons-material/Check';
import Divider from '@mui/material/Divider';
import Tooltip from '@mui/material/Tooltip';

import { VERSION, COMMIT_HASH } from './environment';

import { PageContext } from './Page';
import { useContext } from 'react';

const drawerWidth = 240;

export default function SideMenu() {

    const context = useContext(PageContext);

    const menuItems = [{
      text: "Home",
      href: context.sandboxId ? `/sandbox/${context.sandboxId}` : "/",
      icon: <HomeIcon />,
      displayText: "Home",
    },
    {
      text: "Dashboard",
      href: context.sandboxId ? `/sandbox/dashboard/${context.sandboxId}` : "/dashboard",
      icon: <CheckIcon />,
      displayText: "Validation",
    },];

    return (
        <Drawer
            variant="permanent"
            sx={{
                width: drawerWidth,
                flexShrink: 0,
                [`& .MuiDrawer-paper`]: { position: 'relative', width: drawerWidth, boxSizing: 'border-box' },
                display: { xs:'none', md: 'flex'},
            }}
        >
            <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'auto' }}>
                <List>
                    {menuItems.map((item) => (
                        <ListItem key={item.text} disablePadding>
                            <ListItemButton
                                href={item.href}
                                sx={{
                                boxShadow:
                                    context.pageTitle === item.text.toLowerCase()
                                    ? 'inset 4px 0 0 #1976d2'
                                    : 'inset 4px 0 0 transparent',
                                }}
                            >
                                <ListItemIcon
                                sx={{
                                    minWidth: 40,
                                    display: 'flex',
                                    justifyContent: 'center',
                                }}
                                >
                                {item.icon}
                                </ListItemIcon>

                                <ListItemText primary={item.displayText} />
                            </ListItemButton>
                            </ListItem>
                    ))}
                </List>

                <List sx={{ mt: 'auto' }}>
                <Divider />
                    <ListItem disablePadding>
                        <Tooltip title="Documentation" placement="right">
                            <ListItemButton href="https://buildingsmart.github.io/validate/index.html" target="_blank" rel="noopener noreferrer">
                                <ListItemIcon sx={{ minWidth: 40, display: 'flex', justifyContent: 'center' }}>
                                    <InfoIcon />
                                </ListItemIcon>
                                <ListItemText primary="Documentation" />
                            </ListItemButton>
                        </Tooltip>
                    </ListItem>
                <Divider />
                    <ListItem key="version" disablePadding>
                        <ListItemButton>
                            <ListItemText style={{ textAlign: 'center' }} primary={`${context["environment"]} ${VERSION || ''} ${COMMIT_HASH ? ' - #' + COMMIT_HASH : ''}`} />
                        </ListItemButton>
                    </ListItem>
                </List>
            </Box>
        </Drawer>
    )
}
