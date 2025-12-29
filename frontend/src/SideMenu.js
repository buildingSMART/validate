import * as React from 'react';
import Box from '@mui/material/Box';
import Drawer from '@mui/material/Drawer';
import Toolbar from '@mui/material/Toolbar';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import HomeIcon from '@mui/icons-material/Home';
import CheckIcon from '@mui/icons-material/Check';
import Divider from '@mui/material/Divider';

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
            <Box sx={{ overflow: 'auto'}}>
                <List>
                    {menuItems.map((item, index) => (
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

                <List style={{ position: "absolute", bottom: "0", width: "100%" }}>
                <Divider />
                    <ListItem key={"test"} disablePadding>
                        <ListItemButton>
                            <ListItemText style={{ textAlign: 'center' }} primary={`${context["environment"]} ${VERSION || ''} ${COMMIT_HASH ? ' - #' + COMMIT_HASH : ''}`} />
                        </ListItemButton>
                    </ListItem>
                </List>
            </Box>
        </Drawer>
    )
}